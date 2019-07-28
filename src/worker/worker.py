import os
import sys
import time
import docker
import signal
import time
import traceback
import datetime as dt

# Set up sentry.
import sentry_sdk
from sentry_sdk import capture_exception
sentry_sdk.init(os.getenv('SENTRY_WORKER_DSN', ''), environment=os.getenv('ENVIRONMENT', 'default'))

def sigterm_handler(signal, frame):
    print('SIGTERM received', flush=True)

    # Gracefully stop container.
    print(container, flush=True)
    if container is not None:
        try:
            print('sending SIGTERM to container {}'.format(container.name),
                  flush=True)
            container.stop()
        except Exception as e:
            capture_exception(e)
            print('error while stopping container', flush=True)
        finally:
            container.remove(force=True)

    sys.exit(0)

# Handle SIGTERM gracefully.
signal.signal(signal.SIGTERM, sigterm_handler)

PARSE_HOSTNAME = os.getenv('PARSE_HOSTNAME', 'http://parse-server:1337/parse')
PARSE_APP_ID = os.getenv('PARSE_APP_ID', 'alaska')
PARSE_MASTER_KEY = os.getenv('PARSE_MASTER_KEY', 'MASTER_KEY')
print(PARSE_HOSTNAME, PARSE_APP_ID, PARSE_MASTER_KEY)

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

from parse_rest.config import Config
from parse_rest.datatypes import Function, Object, Date
from parse_rest.connection import register
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import ParseBatcher
from parse_rest.core import ResourceRequestBadRequest, ParseError
register(PARSE_APP_ID, '', master_key=PARSE_MASTER_KEY)

def dequeue():
    try:
        Job = Object.factory('Job')
        jobs = Job.Query.filter(queuePosition__gte=0).order_by('queuePosition').limit(1)

        if jobs:
            job = jobs[0]
            Function('jobStarted')(objectId=job.objectId)
            return Job.Query.get(objectId=job.objectId)
        else:
            return False
    except Exception as e:
        capture_exception(e)

def wait():
    # Get wait time.
    interval = Config.get()['workerInterval']
    time.sleep(interval)

def check_images():
    index_image = Config.get()['indexImage']

    Analysis = Object.factory('Analysis')
    images = list(analysis.image for analysis in Analysis.Query.filter(active=True)) + [index_image]

    client = docker.from_env()

    for image in images:
        print(image, flush=True)
        try:
            client.images.get(image)
        except Exception as e:
            capture_exception(e)
            print('error while checking image {}'.format(image))
            sys.exit(1)


# Global variable for container.
container = None
def start():
    global container

    while True:
        # Dequeue job.
        job = dequeue()

        if job:
            try:
                project = job.project
                analysis = job.analysis
                print('Retrieved job {} for project {}'.format(job.objectId,
                                                               project.objectId),
                      flush=True)

                # Make directory if it doesn't exist.
                if analysis.code not in project.paths:
                    path = os.path.join(project.paths['root'], analysis.code)
                    os.makedirs(path, exist_ok=True)

                    project.paths[analysis.code] = path
                    project.save()
                # Also for each sample, if it needs one.
                if analysis.type == 'sample':
                    samples = project.relation('samples').query()

                    for sample in samples:
                        if analysis.code not in sample.paths:
                            path = os.path.join(project.paths[analysis.code], sample.name)
                            os.makedirs(path, exist_ok=True)

                            sample.paths[analysis.code] = path
                            sample.save()


                config = Config.get()
                data_volume = config['repoName'] + '_' + config['dataVolume']
                data_path = config['dataPath']
                script_volume = config['repoName'] + '_' + config['scriptVolume']
                script_path = config['scriptPath']
                network = config['repoName'] + '_' + config['backendNetworkName']
                cpus = config['cpus']

                # begin container variables.
                cmd = 'python3 -u {} {} {}'.format(analysis.script,
                                                   project.objectId,
                                                   analysis.code)
                if getattr(analysis, 'requires', None) is not None:
                    cmd += ' ' + analysis.requires.code
                if job.archive:
                    cmd += ' --archive'

                volumes = {
                    data_volume: {'bind': data_path, 'mode': 'rw'},
                    script_volume: {'bind': script_path, 'mode': 'rw'}
                }
                environment = {
                    'PARSE_HOSTNAME': PARSE_HOSTNAME,
                    'PARSE_APP_ID': PARSE_APP_ID,
                    'PARSE_MASTER_KEY': PARSE_MASTER_KEY,
                    'ENVIRONMENT': os.getenv('ENVIRONMENT', 'default'),
                    'SENTRY_QC_DSN': os.getenv('SENTRY_QC_DSN', ''),
                    'SENTRY_QUANT_DSN': os.getenv('SENTRY_QUANT_DSN', ''),
                    'SENTRY_DIFF_DSN': os.getenv('SENTRY_DIFF_DSN', ''),
                    'SENTRY_POST_DSN': os.getenv('SENTRY_POST_DSN', '')
                }
                wdir = script_path
                name = '{}-{}'.format(analysis.code, project.objectId)

                # output path.
                output_file = '{}_output.txt'.format(analysis.code)
                output_path = os.path.join(project.paths[analysis.code], output_file)
                job.outputPath = output_path
                start = time.time()
                job.save()

                # Remove output file if it already exists.
                if os.path.exists(output_path):
                    os.remove(output_path)

                progress = config['progress']
                key = analysis.code + '_started'
                if key in progress:
                    project.oldProgress = progress[key]
                    project.save()

                # Docker client.
                client = docker.from_env()
                container = client.containers.run(analysis.image, cmd, detach=True,
                                                  auto_remove=True, volumes=volumes,
                                                  working_dir=wdir, cpuset_cpus=cpus,
                                                  network=network, environment=environment,
                                                  name=name)
                print('started container with id {} and name {}'.format(container.id, name))
                hook = container.logs(stdout=True, stderr=True, stream=True)
                for line in hook:
                    decoded = line.decode('utf-8').strip().encode('ascii', 'ignore').decode('ascii')

                    if '\n' in decoded:
                        outs = decoded.split('\n')
                    else:
                        outs = [decoded]

                    for out in outs:
                        # Detect commands.
                        if out.startswith('##'):
                            job.commands.append(out.strip('# '))
                            job.save()

                        # Save output.
                        print(out, flush=True)
                        with open(output_path, 'a') as f:
                            f.write(out + '\n')

                # Container finished.
                exitcode = container.wait()['StatusCode']
                runtime = time.time() - start

                if exitcode != 0:
                    log = container.attach(stdout=True, stderr=True, stream=False, logs=True)
                    msg = 'container {} exited with code {}\n{}'.format(name, exitcode, log)
                    raise Exception(msg)
                else:
                    print('{} success'.format(container.name))
                    Function('jobSuccess')(objectId=job.objectId, runtime=runtime)
                    continue
            except Exception as e:
                capture_exception(e)
                print(traceback.format_exc(), file=sys.stderr, flush=True)

                # Notify that there was an error.
                Function('jobError')(objectId=job.objectId)

            finally:
                container = None

        # Wait.
        wait()


if __name__ == '__main__':
    time.sleep(5)

    # Check images.
    check_images()

    start()
