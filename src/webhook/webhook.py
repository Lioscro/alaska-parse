import os
import sys
import re
import time
import json
import string
import random
import signal
import string
import docker
import shutil
import hashlib
import traceback
import datetime as dt
from threading import Thread

# import docker
from flask import Flask, request, jsonify, send_file, send_from_directory
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
from parse_rest.connection import register, SessionToken
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import ParseBatcher
from parse_rest.core import ResourceRequestBadRequest, ParseError
register(PARSE_APP_ID, '', master_key=PARSE_MASTER_KEY)

sys.path.append(Config.get()['scriptPath'])
from compile import compile
from upload import upload

compiling = {}
uploading = {}
index_container = None
def sigterm_handler(signal, frame):
    print('SIGTERM received', file=sys.stderr, flush=True)
    print(compiling, uploading, file=sys.stderr, flush=True)

    Project = Object.factory('Project')

    for objectId, t in compiling.items():
        if t.is_alive():
            project = Project.Query.get(objectId=objectId)
            project.progress = 'success'
            project.save()


    for objectId, t in uploading.items():
        if t.is_alive():
            project = Project.Query.get(objectId=objectId)
            project.progress = 'compiled'
            project.save()

    if index_container is not None:
        try:
            print('sending SIGTERM to container {}'.format(index_container.name),
                  flush=True)
            index_container.stop()
        except Exception as e:
            print('error while stopping container', flush=True)
        finally:
            index_container.remove(force=True)

    sys.exit(0)


# Handle SIGTERM gracefully.
signal.signal(signal.SIGTERM, sigterm_handler)

# Actual flask application.
app = Flask(__name__)

@app.route('/index', methods=['POST'])
def index():
    return jsonify({'success': 'hello'})

# For debugging.
@app.route('/status', methods=['POST'])
def status():
    return jsonify({'success': 'online'})

verified = []
verification = {}

@app.route('/email/verified', methods=['POST'])
def email_verified():
    data = request.get_json()
    email = data['email']

    if email in verified:
        return jsonify({'result': True})
    return jsonify({'result': False})

@app.route('/email/verify/<key>', methods=['GET', 'POST'])
def verify_email(key):
    if key in verification:
        verified.append(verification[key])
        del verification[key]
    else:
        return jsonify({'result': 'invalid verification key'})

    return jsonify({'result': 'verified'})

@app.route('/email/verification', methods=['POST'])
def send_verification_email():
    data = request.get_json()
    to = data['email']
    fr = 'verify@alaska.caltech.edu'
    datetime = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    config = Config.get()
    host = config['host']
    data_path = config['dataPath']
    email_dir = config['emailDir']
    email_path = os.path.join(data_path, email_dir)
    key = ''
    for i in range(24):
        key += str(random.choice(string.digits))
    verification[key] = to

    url = 'http://{}/webhook/email/verify/{}'.format(host, key)

    subject = 'Email verification for Alaska'
    message = ('Please click on the following link to complete verification.<br>'
               '<a href="{}">{}</a><br>'
               'If you did not request verification, please do not click on the link.').format(url, url)

    email = {'to': to,
             'from': fr,
             'subject': subject,
             'message': message}

    email_file = '{}.json'.format(datetime)
    output_path = os.path.join(email_path, email_file)

    with open(output_path, 'w') as f:
        json.dump(email, f, indent=4)

    return jsonify({'result': email_file})

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

                    if genus not in organisms:
                        organisms[genus] = {}
                    if species not in organisms[genus]:
                        organisms[genus][species] = organism
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
    index_container = client.containers.run(index_image, cmd, detach=False, stderr=True,
                                      auto_remove=True, volumes=volumes,
                                      working_dir=wdir, cpuset_cpus=cpus,
                                      network=network, environment=environment,
                                      name=name)
    index_container = None

@app.route('/project/<objectId>/initialize', methods=['POST'])
def project_initialize(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            return _project_initialize(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/ftp', methods=['POST'])
def project_ftp(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            return _project_ftp(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/compile', methods=['POST'])
def project_compile(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            if objectId in compiling and compiling[objectId].is_alive():
                raise Exception('{} is already being compiled'.format(objectId))

            Project = Object.factory('Project')
            project = Project.Query.get(objectId=objectId)
            project.progress = 'compiling'
            project.save()

            t = Thread(target=_project_compile, args=(project,))
            t.daemon = True
            compiling[objectId] = t
            t.start()

            return jsonify({'result':'compiling'})
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/upload', methods=['POST'])
def project_upload(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            data = request.get_json()
            host = data['host']
            username = data['username']
            password = data['password']
            geo_username = data['geo_username']

            Project = Object.factory('Project')
            project = Project.Query.get(objectId=objectId)
            project.progress = 'uploading'
            project.save()

            if objectId in uploading and uploading[objectId].is_alive():
                raise Exception('{} is already being uploaded'.format(objectId))

            t = Thread(target=_project_upload, args=(project, host, username, password, geo_username,))
            t.daemon = True
            uploading[objectId] = t
            t.start()

            return jsonify({'result': 'uploading'})

    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})


@app.route('/project/<objectId>/delete', methods=['POST'])
def project_delete(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            return _project_delete(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/citation', methods=['POST'])
def project_citation(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            return _project_citation(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/file/<code>', defaults={'name': None}, methods=['GET'])
@app.route('/project/<objectId>/file/<code>/<name>', methods=['GET'])
def project_get(objectId, code, name):
    try:
        token = request.args.get('sessionToken')

        # Check session token.
        with SessionToken(token):
            return _project_get(objectId, code, name)
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

@app.route('/project/<objectId>/sleuth/<int:port>', methods=['POST'])
def project_sleuth(objectId, port):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            return _project_sleuth(objectId, port)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/sleuth/close', methods=['POST'])
def project_sleuth_close(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
            return _project_sleuth_close(objectId)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/project/<objectId>/reads', methods=['POST'])
def project_reads(objectId):
    try:
        token = request.args.get('sessionToken')
        with SessionToken(token):
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
        token = request.args.get('sessionToken')
        with SessionToken(token):
            name = request.args.get('name')
            return _sample_initialize(projId, objectId, name)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

@app.route('/sample/<objectId>/citation', methods=['POST'])
def sample_citation(objectId):
    try:
        return _sample_citation(objectId)
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
    ftp_path = config['ftpPath']
    project_archive = config['projectArchive']

    # Make directories.
    root_path = os.path.join(data_path, project_dir, objectId)
    read_path = os.path.join(root_path, read_dir)
    ftp_project_path = os.path.join(ftp_path, project_dir, objectId)
    ftp_read_path = os.path.join(ftp_project_path, read_dir)
    paths = {'root': root_path,
             'read': read_path}

    # Make sure this is actually a new project.
    if os.path.exists(root_path):
        return jsonify({'error': 'root folder exists'})

    for _, path in paths.items():
        os.makedirs(path, exist_ok=True)

    # Make UPLOAD_HERE file
    upload_here = os.path.join(read_path, 'UPLOAD_HERE')
    with open(upload_here, 'w') as f:
        f.write('')

    # Make ftp user.
    # Generate random password
    passwd = _generate_password(5)

    # begin container variables
    cmd = ('/bin/bash -c "chmod -R 0777 {} && (echo {}; echo {}) | pure-pw useradd {} -m -f /etc/pure-ftpd/passwd/pureftpd.passwd '
          + '-u ftpuser -d {}"').format(ftp_project_path, passwd, passwd, objectId, ftp_read_path)
    print(cmd, file=sys.stderr)

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

def _project_ftp(objectId):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    config = Config.get()
    ftp_path = config['ftpPath']
    project_dir = config['projectDir']
    ftp_project_path = os.path.join(ftp_path, project_dir, objectId)

    # Change ftp home directory to the project root.
    cmd = ('pure-pw usermod {} -d {} -m -f /etc/pure-ftpd/passwd/pureftpd.passwd').format(objectId, ftp_project_path)
    try:
        ftp_name = config['repoName'] + '_' + config['ftpService'] + '_1'
        client = docker.from_env()
        ftp = client.containers.get(ftp_name)

        # run command.
        out = ftp.exec_run(cmd)
        exit_code = out[0]

        if exit_code != 0:
            raise Exception('non-zero exit code on ftp user modification')
    except Exception as e:
        print('error occured while modifying ftp user {}'.format(objectId), file=sys.stderr)
        raise e

    return jsonify({'result': project.paths['root']})

def _project_delete(objectId):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    try:
        if os.path.isdir(project.paths['root']):
            shutil.rmtree(project.paths['root'])
    except Exception as e:
        print(e)

    return jsonify({'result': 'success'})

def _job_output(objectId):
    # Get job from server.
    Job = Object.factory('Job')
    job = Job.Query.get(objectId=objectId)

    output = None
    with open(job.outputPath, 'r') as f:
        output = f.readlines()

    return jsonify({'result': output})

def _sample_citation(objectId):
    # Get project from server.
    Sample = Object.factory('Sample')
    sample = Sample.Query.get(objectId=objectId)

    config = Config.get()

    genus = sample.reference.organism.genus
    species = sample.reference.organism.species
    ref_version = sample.reference.version

    arg = '-b {} --bias'.format(config['kallistoBootstraps'])

    if sample.readType == 'single':
        arg += ' --single -l {} -s {}'.format(sample.readLength,
                                              sample.readStd)

    format_dict = {'genus': genus,
                   'species': species,
                   'ref_version': ref_version,
                   'arg': arg,
                   **config}

    info = ['RNA-seq data was analyzed with the Alaska pipeline (alaska.caltech.edu).',
            ('Quality control was performed using using Bowtie2 (v{versionBowtie}), '
             'Samtools (v{versionSamtools}), RSeQC (v{versionRseqc}), '
             'FastQC (v{versionFastqc}), with results aggregated with '
             'MultiQC (v{versionMultiqc}).').format(**format_dict),
            ('Reads were aligned to the {genus} {species} genome version {ref_version} '
             'as provided by Wormbase using Kallisto (v{versionKallisto}) with the following '
             'flags: {arg}').format(**format_dict),
            ('Differential expression analyses with Sleuth (v{versionSleuth}) '
             'were performed using a Wald Test corrected for multiple-testing.').format(**format_dict)]

    if genus == 'caenorhabditis' and species == 'elegans':
        info.append('Enrichment analysis was performed using the Wormbase Enrichment Suite.')

    return jsonify({'result': info})

def _project_citation(objectId):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    config = Config.get()
    citation_file = config['citationFile']
    citation_path = os.path.join(project.paths['root'], citation_file)

    samples = project.relation('samples').query()

    args = ''
    genus = ''
    species = ''
    ref_version = ''
    for sample in samples:
        genus = sample.reference.organism.genus
        species = sample.reference.organism.species
        ref_version = sample.reference.version

        arg = '-b {} --bias'.format(config['kallistoBootstraps'])

        if sample.readType == 'single':
            arg += ' --single -l {} -s {}'.format(sample.readLength,
                                                  sample.readStd)

        args += '{}({}):\t{}.\n'.format(sample.objectId, sample.name, arg)


    format_dict = {'factor': str(len(project.factors)),
                   'genus': genus.capitalize(),
                   'species': species,
                   'ref_version': ref_version,
                   'args': args,
                   'datetime': project.createdAt,
                   'id': project.objectId,
                   'n_samples': len(project.relation('samples').query()),
                   **config}

    info = ('alaska_info.txt for {id}\n'
            'This project was created on {datetime} PST with '
            '{n_samples} samples.\n\n').format(**format_dict)

    info += ('RNA-seq data was analyzed with Alaska using the '
        '{factor}-factor design option.\nBriefly, Alaska '
        'performs quality control using\nBowtie2 (v{versionBowtie}), '
        'Samtools (v{versionSamtools}), RSeQC (v{versionRseqc}), '
        'FastQC (v{versionFastqc}) and outputs\n'
        'a summary report generated using MultiQC (v{versionMultiqc}). Read '
        'quantification and\ndifferential expression analysis of '
        'transcripts were performed using\nKallisto (v{versionKallisto}) '
        'and Sleuth (v{versionSleuth}), respectively. '
        'Kallisto (v{versionKallisto}) was run using the\nfollowing flags for each '
        'sample:\n{args}\n'
        'Reads were aligned using\n{genus} {species} genome '
        'version {ref_version}\nas provided by Wormbase.\n\n'
        'Differential expression analyses with Sleuth (v{versionSleuth}) were '
        'performed using a\nWald Test corrected for '
        'multiple-testing.\n\n').format(**format_dict)

    # Add more info if enrichment analysis was performed.
    if genus == 'caenorhabditis' and species == 'elegans':
        info += ('Enrichment analysis was performed using the WormBase '
                 'Enrichment Suite:\n'
                 'https://doi.org/10.1186/s12859-016-1229-9\n'
                 'https://www.wormbase.org/tools/enrichment/tea/tea.cgi\n')
    # if self.epistasis:
    #     info += ('Alaska performed epistasis analyses as first '
    #              'presented in\nhttps://doi.org/10.1073/pnas.1712387115\n')

    with open(citation_path, 'w') as f:
        f.write(info)

    project.files['citation'] = citation_path
    project.save()

    return jsonify({'result': info})

def _project_compile(project):
    objectId = project.objectId

    with app.app_context():
        try:
            _project_email(objectId, 'Compilation started for project {}'.format(objectId),
                           'Alaska has started compiling project {} for GEO submission.'.format(objectId))

            compile(project)

            project.progress = 'compiled'
            project.save()

            _project_email(objectId, 'Compilation finished for project {}'.format(objectId),
                           ('Alaska has finished compiling project {} for GEO submission. '
                            'Please visit the unique URL to submit.').format(objectId))
        except Exception as e:
            project.progress = 'success'
            project.save()
            _project_email(objectId, 'Compiliation failed for project {}'.format(objectId),
                           ('Alaska encountered an error while compiling project {} for GEO submission.'
                            '<br>{}<br>'
                            'Please submit an issue on Github if '
                            'this keeps happening.').format(objectId, str(e)))

def _project_upload(project, host, username, password, geo_username):
    objectId = project.objectId
    with app.app_context():
        try:
            _project_email(objectId, 'Submission started for project {}'.format(objectId),
                           ('Alaska has started submitting project {} to the GEO. '
                            'You may view the progress of your upload through the '
                            'public GEO FTP.').format(objectId))

            file = '{}_files.tar.gz'.format(geo_username)
            upload(project, host, username, password, file)

            # Once done, update progress.
            project.progress = 'uploaded'
            project.save()

            _project_email(objectId, 'Submission finished for project {}'.format(objectId),
                           ('Alaska has finished submission of project {} to the GEO.<br>'
                            'Please fill out this form: <a href="mailto:{}">GEO submission form</a> '
                            'with the following information:<br>'
                            '1) Select <i>Notify GEO about your FTP file transfer</i><br>'
                            '2) Select <i>Yes, all my data have finished transferring</i><br>'
                            '3) The name of the uploaded file is: <strong>{}</strong><br>'
                            '4) Select <i>New</i> as the submission kind.<br>'
                            '5) Select your preferred release date.<br>'
                            'Failure to submit this form may result in the removal '
                            'of your data!').format(objectId, Config.get()['geoForm'], file))
        except Exception as e:
            project.progress = 'compiled'
            project.save()
            _project_email(objectId, 'Upload failed for project {}'.format(objectId),
                           ('Alaska encountered an error while uploading project {} to the GEO.'
                            '<br>{}<br>'
                            'Please submit an issue on Github if '
                            'this keeps happening.').format(objectId, str(e)))

def _project_get(objectId, code, name):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    if name:
        path = project.files[code][name]
    else:
        path = project.files[code]

    print(path, file=sys.stderr)

    # If the file is an html file, serve it as a static file.
    # Otherwise, send it as a file.
    extension = '.'.join(path.split('.')[1:])
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    if extension == 'html':
        return send_from_directory(dirname, basename)

    if name:
        filename = '{}_{}_{}.{}'.format(objectId, code, name, extension)
    else:
        filename = '{}_{}.{}'.format(objectId, code, extension)
    return send_from_directory(dirname, basename, as_attachment=True,
                               attachment_filename=filename)

def _project_sleuth(objectId, port):
    # Get project from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    # Check if there is a sleuth container open for this project.
    config = Config.get()
    data_volume = config['repoName'] + '_' + config['dataVolume']
    data_path = config['dataPath']
    script_volume = config['repoName'] + '_' + config['scriptVolume']
    script_path = config['scriptPath']
    network = config['repoName'] + '_' + config['backendNetworkName']
    shiny_script = config['shinyScript']
    so_path = project.files[config['diffDir']]['sleuth']

    # Start a new docker container.
    cmd = 'Rscript {} -p {} --alaska'.format(shiny_script, so_path)
    volumes = {
        data_volume: {'bind': data_path, 'mode': 'rw'},
        script_volume: {'bind': script_path, 'mode': 'rw'}
    }
    environment = {
        'PARSE_HOSTNAME': PARSE_HOSTNAME,
        'PARSE_APP_ID': PARSE_APP_ID,
        'PARSE_MASTER_KEY': PARSE_MASTER_KEY
    }
    ports = {
        42427: port
    }
    wdir = script_path
    name = 'shiny-{}'.format(project.objectId)

    # Docker client.
    client = docker.from_env()
    container = client.containers.run(config['diffImage'], cmd, detach=True,
                                      auto_remove=True, volumes=volumes,
                                      working_dir=wdir, network=network,
                                      environment=environment, name=name,
                                      ports=ports)

    return jsonify({'result': {'containerId': container.id, 'containerName': name}})

def _project_sleuth_close(objectId):
    # Get shiny from server.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)
    shiny = project.shiny

    container_id = shiny.containerId
    container_name = shiny.containerName

    # Docker client.
    client = docker.from_env()
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=1)
        return jsonify({'result': 'stopped'})
    except docker.errors.NotFound:
        return jsonify({'result': 'not found'})


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

@app.route('/project/<objectId>/email', methods=['POST'])
def project_email(objectId):
    try:
        data = request.get_json()
        subject = data['subject']
        message = data['message']
        print(subject, message, file=sys.stderr, flush=True)
        return _project_email(objectId, subject, message)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({'error': str(e)})

def _project_email(objectId, subject, message):
    """
    Send mail with the given arguments.
    """
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    config = Config.get()
    host = config['host']
    data_path = config['dataPath']
    email_dir = config['emailDir']
    email_path = os.path.join(data_path, email_dir)

    datetime = (dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                + ' Pacific Time')
    url = 'http://{}/?id={}'.format(host, objectId)
    fr = 'AlaskaProject_{}@{}'.format(objectId, host)
    to = project.email

    format_dict = {'message': message,
                   'objectId': objectId,
                   'url': url,
                   'host': host,
                   'password': project.ftpPassword,
                   'to': to,
                   'datetime': datetime}

    # Footer that is appended to every email.
    full_message = '\
    <html> \
        <head></head> \
        <body> \
         <p>{message}</p> \
         <br> \
         <hr> \
         <p>Project ID: {objectId}<br> \
         Unique URL: <a href="{url}">{url}</a><br> \
         FTP server: {host}<br> \
         FTP port: 21<br> \
         FTP username: {objectId}<br> \
         FTP password: {password}<br> \
         This message was sent to {to} at {datetime}.<br> \
         <b>Please do not reply to this email.</b></p> \
        </body> \
    </html> \
    '.format(**format_dict)

    email = {'to': to,
             'from': fr,
             'subject': subject,
             'message': full_message}

    email_file = '{}.json'.format(datetime)
    output_path = os.path.join(email_path, email_file)

    with open(output_path, 'w') as f:
        json.dump(email, f, indent=4)

    return jsonify({'result': email_file})

def cleanup_progress():
    print('cleaning up progresses')
    Project = Object.factory('Project')
    projects = Project.Query.all().filter(progress='compiling')
    print(projects)
    for project in projects:
        project.progress = 'success'
        project.save()

    projects = Project.Query.all().filter(progress='uploading')
    print(projects)
    for project in projects:
        project.progress = 'compiled'
        project.save()

if __name__ == '__main__':
    print('Waiting 5 seconds for server.')
    time.sleep(5)

    # Cleanup progress.
    cleanup_progress()

    app.run(debug=True, host='0.0.0.0')
