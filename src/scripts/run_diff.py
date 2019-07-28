import os
import sentry_sdk
sentry_sdk.init(os.getenv('SENTRY_DIFF_DSN', ''))
from sentry_sdk import configure_scope

import pandas as pd
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

def write_matrix(project, code='diff'):
    samples = project.relation('samples').query()
    factors = list(project.factors.keys())
    labels = project.factors
    controls = project.controls

    rows = []
    for sample in samples:
        row = [sample.name]
        for factor in factors:
            if sample.metadata[factor] == controls[factor]:
                row.append('control-{}'.format(controls[factor]))
            else:
                row.append('test-{}'.format(sample.metadata[factor]))
        rows.append(row)

    matrix = pd.DataFrame(data=rows, columns=['sample'] + factors)

    sleuth_matrix = Config.get()['sleuthMatrix']
    matrix_path = os.path.join(project.paths[code], sleuth_matrix)
    matrix.to_csv(matrix_path, sep=' ', index=False)

    if code not in project.files:
        project.files[code] = {}
    project.files[code]['matrix'] = matrix_path
    project.save()


def run_sleuth(project, code='diff', requires='quant'):
    print_with_flush('# starting sleuth for project {}'.format(project.objectId))

    config = Config.get()

    script_path = config['scriptPath']
    sleuth_script = config['sleuthScript']
    sleuth_object = config['sleuthObject']
    sleuth_path = os.path.join(script_path, sleuth_script)
    object_path = os.path.join(project.paths[code], sleuth_object)

    diff_path = project.paths[code]

    samples = list(project.relation('samples').query())

    args = ['Rscript', sleuth_path]
    args += ['-d', project.paths[code]]
    args += ['-k', project.paths[requires]]
    args += ['-o', project.paths[code]]
    args += ['-a', samples[0].reference.paths['annotation']]

    run_sys(args, prefix=project.objectId)

    # Archive.
    archive_path = archive(project, code)

    if code not in project.files:
        project.files[code] = {}
    project.files[code]['sleuth'] = object_path
    project.files[code]['archive'] = archive_path
    project.save()

    print_with_flush('# done')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Perform diff.')
    parser.add_argument('objectId', type=str)
    parser.add_argument('code', type=str, default='diff')
    parser.add_argument('requires', type=str, default='quant')
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()

    objectId = args.objectId

    with configure_scope() as scope:
        scope.user = {'id': objectId}
        code = args.code
        requires = args.requires

        # Get project with specified objectId.
        Project = Object.factory('Project')
        project = Project.Query.get(objectId=objectId)

        # Write matrix.
        write_matrix(project, code=code)

        # Run sleuth
        run_sleuth(project, code=code, requires=requires)

        # If archive = true:
        if args.archive:
            archive_path = archive_project(project, '{}_{}'.format(project.objectId, Config.get()['projectArchive']))
            project.files['archive'] = archive_path
            project.save()
