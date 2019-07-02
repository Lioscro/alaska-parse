import os
import sys
import re
import json
import random
import string
import docker
import shutil
import hashlib
import traceback
# import docker
from flask import Flask, request, jsonify, send_file
from urllib.parse import unquote_plus
from threading import Thread

PARSE_HOSTNAME = os.getenv('PARSE_HOSTNAME', 'http://parse-server:1337/parse')
PARSE_APP_ID = os.getenv('PARSE_APP_ID', 'alaska')
PARSE_MASTER_KEY = os.getenv('PARSE_MASTER_KEY', 'MASTER_KEY')
print(PARSE_HOSTNAME, PARSE_APP_ID, PARSE_MASTER_KEY)

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

from parse_rest.config import Config
from parse_rest.datatypes import Function, Object, GeoPoint
from parse_rest.connection import register
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import ParseBatcher
from parse_rest.core import ResourceRequestBadRequest, ParseError
register(PARSE_APP_ID, '', master_key=PARSE_MASTER_KEY)

# Actual flask application.
app = Flask(__name__)

@app.route('/index', methods=['POST'])
def index():
    return jsonify({'success': 'hello'})

# For debugging.
@app.route('/status', methods=['POST'])
def status():
    return jsonify({'success': 'online'})

@app.route('/reference/new', methods=['POST'])
def organismNew():
    '''
    Method to scan for new organisms.
    '''
    print('scanning for new organisms', file=sys.stderr)

    config = Config.get()
    data_path = config['dataPath']
    reference_dir = config['referenceDir']
    kallisto_dir = config['kallistoIndexDir']
    bowtie_dir = config['bowtieIndexDir']
    organism_dir = config['organismDir']
    organism_path = os.path.join(data_path, organism_dir)

    # Make the directory in case it doesn't exist.
    os.makedirs(organism_path, exist_ok=True)

    organisms = Function('getOrganismsDict')()['result']

    for genus in os.listdir(organism_path):
        genus_path = os.path.join(organism_path, genus)
        if not os.path.isdir(genus_path):
            continue

        for species in os.listdir(genus_path):
            species_path = os.path.join(genus_path, species)
            if not os.path.isdir(species_path):
                continue

            for version in os.listdir(species_path):
                version_path = os.path.join(species_path, version)
                reference_path = os.path.join(version_path, reference_dir)
                if not os.path.isdir(reference_path):
                    continue

                # Make new organism.
                Organism = Object.factory('Organism')
                if genus not in organisms or species not in organisms[genus]:
                    organism = Organism(genus=genus, species=species,
                                        path=species_path)
                    organism.save()
                else:
                    # Otherwise, the organism already exists.
                    found = Organism.Query.filter(genus=genus, species=species)
                    assert(len(found) == 1)
                    organism = found[0]

                # Get all reference versions.
                references = organism.relation('references').query()
                versions = [reference.version for reference in references]

                if version not in versions:
                    # Get reference files.
                    bed = None
                    annotation = None
                    cdna = None
                    dna = None
                    for fname in os.listdir(reference_path):
                        path = os.path.join(reference_path, fname)
                        if fname.endswith('.bed'):
                            bed = path
                        elif '_annotation' in fname:
                            annotation = path
                        elif '_cdna' in fname:
                            cdna = path
                        elif '_dna' in fname:
                            dna = path

                    if bed and annotation and cdna and dna:
                        print('found {}-{}-{}'.format(genus, species, version),
                              file=sys.stderr)

                        index_prefix = '{}_{}_{}'.format(genus, species, version)
                        kallisto_index_name = index_prefix + '.idx'
                        kallisto_index_path = os.path.join(version_path,
                                                           kallisto_dir,
                                                           kallisto_index_name)
                        bowtie_index_path = os.path.join(version_path,
                                                         bowtie_dir,
                                                         index_prefix)

                        # Paths.
                        paths = {'root': version_path,
                                 'dna': dna,
                                 'cdna': cdna,
                                 'bed': bed,
                                 'annotation': annotation,
                                 'kallistoIndex': kallisto_index_path,
                                 'bowtieIndex': bowtie_index_path}

                        # Make new reference.
                        Reference = Object.factory('Reference')
                        reference = Reference(version=version,
                                              organism=organism,
                                              paths=paths,
                                              indexBuilt=False,
                                              ready=False)
                        reference.save()
                        organism.relation('references').add([reference])

    return jsonify({'status': 'done'})


indexThread = None
@app.route('/reference/build', methods=['POST'])
def referenceBuild():
    '''
    Method to build all non-built references new organisms.
    '''
    global indexThread

    # Get all non-ready references.
    if indexThread is not None and indexThread.is_alive():
        return jsonify({'status': 'running'})

    Reference = Object.factory('Reference')
    references = Reference.Query.filter(ready=False)

    print(references, file=sys.stderr)
    print('found {} unbuilt reference'.format(len(references)), file=sys.stderr)

    indexThread = Thread(target=_referencesBuild, args=(references,))
    indexThread.daemon = True
    indexThread.start()

    return jsonify({'status': 'started'})

def _referencesBuild(references):
    '''
    Function that is called by the thread.
    '''
    for reference in references:
        try:
            _referenceBuild(reference)
        except Exception as e:
            print('error while building reference {}'.format(reference.objectId),
                  file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

    # Set indexThread to None.
    indexThread = None

def _referenceBuild(reference):
    '''
    Helper function that blocks until the given reference is built.
    '''
    # Make sure the index hasn't been built yet.
    if reference.ready:
        return

    config = Config.get()
    index_image = config['indexImage']
    data_volume = config['repoName'] + '_' + config['dataVolume']
    data_path = config['dataPath']
    script_volume = config['repoName'] + '_' + config['scriptVolume']
    script_path = config['scriptPath']
    script = config['indexScript']
    network = config['repoName'] + '_' + config['backendNetworkName']
    cpus = config['cpus']

    # begin container variables
    cmd = 'python3 {} {}'.format(script, reference.objectId)
    volumes = {
        data_volume: {'bind': data_path, 'mode': 'rw'},
        script_volume: {'bind': script_path, 'mode': 'rw'}
    }
    environment = {
        'PARSE_HOSTNAME': PARSE_HOSTNAME,
        'PARSE_APP_ID': PARSE_APP_ID,
        'PARSE_MASTER_KEY': PARSE_MASTER_KEY
    }
    wdir = script_path
    name = 'index-{}'.format(reference.objectId)

    print(cmd, volumes, wdir, file=sys.stderr)

    # Docker client.
    client = docker.from_env()
    container = client.containers.run(index_image, cmd, detach=False, stderr=True,
                                      auto_remove=True, volumes=volumes,
                                      working_dir=wdir, cpuset_cpus=cpus,
                                      network=network, environment=environment,
                                      name=name)

@app.route('/project/<objectId>/initialize', methods=['POST'])
def project_initialize(objectId):
    try:
        return _project_initialize(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/delete', methods=['POST'])
def project_delete(objectId):
    try:
        return _project_delete(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/download', defaults={'code': None}, methods=['POST'])
@app.route('/project/<objectId>/download/<code>', methods=['POST'])
def project_download(objectId, code):
    try:
        return _project_download(objectId, code)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/job/<objectId>/output', methods=['POST'])
def job_output(objectId):
    try:
        return _job_output(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/sleuth', methods=['POST'])
def project_sleuth(objectId):
    try:
        return _project_sleuth(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/reads', methods=['POST'])
def project_reads(objectId):
    try:
        return _project_reads(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/read/md5', methods=['POST'])
def read_md5():
    try:
        path = request.args.get('path')
        print(path, file=sys.stderr)
        return _read_md5(path)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/read/delete', methods=['POST'])
def read_delete():
    try:
        path = request.args.get('path')
        print(path, file=sys.stderr)
        return _read_delete(path)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<projId>/sample/<objectId>/initialize', methods=['POST'])
def sample_initialize(projId, objectId):
    try:
        name = request.args.get('name')
        return _sample_initialize(projId, objectId, name)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

def _get_analyses():
    # Get all active analyses.
    Analysis = Object.factory('Analysis')
    return Analysis.Query.all().filter(active=True)

def _generate_password(l):
    choices = string.ascii_lowercase + string.digits
    return ''.join(random.choice(choices) for i in range(l))

def _project_initialize(objectId):
    config = Config.get()
    data_path = config['dataPath']
    project_dir = config['projectDir']
    read_dir = config['readDir']
    project_archive = config['projectArchive']

    # Make directories.
    root_path = os.path.join(data_path, project_dir, objectId)
    read_path = os.path.join(root_path, read_dir)
    paths = {'root': root_path,
             'read': read_path}

    # Make sure this is actually a new project.
    if os.path.exists(root_path):
        return jsonify({'error': 'root folder exists'})

    for _, path in paths.items():
        os.makedirs(path, exist_ok=True)

    # Make ftp user.
    # Generate random password
    passwd = _generate_password(5)

    # begin container variables
    cmd = ('/bin/bash -c "(echo {}; echo {}) | pure-pw useradd {} -m '
          + '-u ftpuser -d {}"').format(passwd, passwd, objectId, read_path)
    print(cmd, file=sys.stderr)

    # Docker client.
    try:
        ftp_name = config['repoName'] + '_' + config['ftpService'] + '_1'
        client = docker.from_env()
        ftp = client.containers.get(ftp_name)

        # run command.
        out = ftp.exec_run(cmd)
        exit_code = out[0]

        if exit_code != 0:
            raise Exception('non-zero exit code on ftp user creation')
    except Exception as e:
        print('error occured while making ftp user {}'.format(objectId), file=sys.stderr)
        raise e

    return jsonify({'result': {'paths': paths, 'ftpPassword': passwd}})

def _project_delete(objectId):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    try:
        if os.path.isdir(project.paths['root']):
            shutil.rmtree(project.paths['root'])
    except:
        pass

    return jsonify({'result': 'success'})

def _job_output(objectId):
    # Get job from server.
    Job = Object.factory('Job')
    job = Job.Query.get(objectId=objectId)

    output = None
    with open(job.outputPath, 'r') as f:
        output = f.readlines()

    return jsonify({'result': output})

def _project_download(objectId, code):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    path = project.files[code]
    return send_file(path, attachment_filename='{}_{}.tar.gz'.format(objectId, code))

def _project_sleuth(objectId):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    # Check if there is a sleuth container open for this project.
    if project.shiny is not None:
        return jsonify({'result': project.shiny.port})
    else:
        config = Config.get()
        data_volume = config['repoName'] + '_' + config['dataVolume']
        data_path = config['dataPath']
        script_volume = config['repoName'] + '_' + config['scriptVolume']
        script_path = config['scriptPath']
        network = config['repoName'] + '_' + config['backendNetworkName']
        shiny_script = config['shinyScript']
        so_path = project.files[config['diffDir']]['sleuth']

        # Start a new docker container.
        cmd = 'Rscript {} {}'.format(shiny_script, so_path)
        volumes = {
            data_volume: {'bind': data_path, 'mode': 'rw'},
            script_volume: {'bind': script_path, 'mode': 'rw'}
        }
        environment = {
            'PARSE_HOSTNAME': PARSE_HOSTNAME,
            'PARSE_APP_ID': PARSE_APP_ID,
            'PARSE_MASTER_KEY': PARSE_MASTER_KEY
        }
        wdir = script_path
        name = 'shiny-{}'.format(project.objectId)

        # Docker client.
        client = docker.from_env()
        container = client.containers.run('alaska-diff', cmd, detach=True,
                                          auto_remove=True, volumes=volumes,
                                          working_dir=wdir, network=network,
                                          environment=environment, name=name)

def _project_reads(objectId):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    extensions = Config.get()['readExtensions']

    reads = {}
    for root, dirs, files in os.walk(project.paths['read']):
        for f in files:
            if f.endswith(tuple(extensions)):
                name = os.path.basename(root.replace(project.paths['read'], ''))

                # In case files are at the root.
                if name == '':
                    name = '/'

                if name not in reads:
                    reads[name] = []

                path = os.path.join(root, f)
                size = os.path.getsize(path)
                reads[name].append({'path': path, 'size': size})
                print(path, file=sys.stderr)

    return jsonify({'result': reads})

def _read_md5(path):
    hash_md5 = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return jsonify({'result': hash_md5.hexdigest()})

def _read_delete(path):
    if os.path.isfile(path):
        os.remove(path)

    return jsonify({'result': 'removed'})

def _sample_initialize(projId, objectId, name):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=projId)

    config = Config.get()
    data_path = config['dataPath']
    sample_dir = config['sampleDir']
    sample_path = os.path.join(data_path, sample_dir, objectId)
    os.makedirs(sample_path, exist_ok=True)

    # Get analyses that apply to samples.
    sample_analyses = _get_analyses().filter(type='sample')

    paths = {}
    for analysis in sample_analyses:
        if analysis.code in project.paths:
            source_path = os.path.join(project.paths[analysis.code], name)
            target_path = os.path.join(sample_path, analysis.code)

            os.makedirs(source_path, exist_ok=True)
            rel_path = os.path.relpath(source_path, os.path.dirname(target_path))
            print(rel_path, target_path, file=sys.stderr)

            os.symlink(rel_path, target_path, target_is_directory=True)

            paths[analysis.code] = source_path

    return jsonify({'result': {'paths': paths}})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
