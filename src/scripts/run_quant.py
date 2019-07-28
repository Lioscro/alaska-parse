import os
import sentry_sdk
sentry_sdk.init(os.getenv('SENTRY_QUANT_DSN', ''), environment=os.getenv('ENVIRONMENT', 'default'))
from sentry_sdk import configure_scope

import tarfile
from utilities import run_sys, print_with_flush, mp_helper, \
                      archive, archive_project

PARSE_HOSTNAME = os.getenv('PARSE_HOSTNAME', 'http://parse-server:1337/parse')
PARSE_APP_ID = os.getenv('PARSE_APP_ID', 'alaska')
PARSE_MASTER_KEY = os.getenv('PARSE_MASTER_KEY', 'MASTER_KEY')

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

from parse_rest.config import Config
from parse_rest.datatypes import Function, Object, GeoPoint
from parse_rest.connection import register
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import ParseBatcher
from parse_rest.core import ResourceRequestBadRequest, ParseError
register(PARSE_APP_ID, '', master_key=PARSE_MASTER_KEY)

def kallisto(sample, nbootstraps, nthreads=1):

    idx_path = sample.reference.paths['kallistoIndex']
    quant_path = sample.paths['quant']
    # Fetch all reads for this sample.
    reads = {read.objectId: read for read in sample.relation('reads').query()}

    args = ['kallisto', 'quant']
    args += ['-i', idx_path]
    args += ['-o', quant_path]
    args += ['-b', nbootstraps]
    args += ['-t', nthreads]
    args += ['--bias']

    # single/paired end
    if sample.readType == 'single':
        args += ['--single']
        args += ['-l', sample.readLength]
        args += ['-s', sample.readStd]
        args += [read.path for _, read in reads.items()]
    elif sample.readType == 'paired':
        for pair in sample.readPairs:
            args += [reads[pair[0]].path, reads[pair[1]].path]

    run_sys(args, prefix=sample.name)


def run_kallisto(project, nbootstraps, code='quant', nthreads=1):
    """
    Runs read quantification with Kallisto.
    Assumes that the indices are in the folder /organisms
    """
    print_with_flush('# starting qc for project {}'.format(project.objectId))
    # Get samples from project.
    samples = project.relation('samples').query()

    for sample in samples:
        print_with_flush('# starting kallisto on sample {}'.format(sample.name))
        kallisto(sample, nbootstraps, nthreads=nthreads)

    # Archive.
    archive_path = archive(project, code)

    if code not in project.files:
        project.files[code] = {}
    project.files[code]['archive'] = archive_path
    project.save()
    print_with_flush('# done')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Perform qc.')
    parser.add_argument('objectId', type=str)
    parser.add_argument('code', type=str, default='quant')
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()

    objectId = args.objectId
    with configure_scope() as scope:
        scope.user = {'id': objectId}

        # Get number of threads.
        config = Config.get()
        nthreads = config['threads']
        nbootstraps = config['kallistoBootstraps']

        code = args.code

        # Get project with specified objectId.
        Project = Object.factory('Project')
        project = Project.Query.get(objectId=objectId)

        # Run kallisto
        run_kallisto(project, nbootstraps, code=code, nthreads=nthreads)

        # If archive = true:
        if args.archive:
            archive_path = archive_project(project, Config.get()['projectArchive'])
            project.files['archive'] = archive_path
            project.save()
