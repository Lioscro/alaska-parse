"""Builds the Bowtie2 and Kallisto indices.

"""

__author__ = 'Kyung Hoi (Joseph) Min'
__copyright__ = 'Copyright 2017 WormLabCaltech'
__credits__ = ['David Angeles', 'Raymond Lee', 'Juancarlos Chan']
__license__ = "MIT"
__version__ = "alpha"
__maintainer__ = "Kyung Hoi (Joseph) Min"
__email__ = "kmin@caltech.edu"
__status__ = "alpha"

import os
import sentry_sdk
sentry_sdk.init(os.getenv('SENTRY_DSN', ''), environment=os.getenv('ENVIRONMENT', 'default'))
from sentry_sdk import configure_scope

import sys
import time
from utilities import run_sys
import datetime as dt
import subprocess as sp

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

def build_bowtie2(reference, nthreads=1):
    """
    Builds bowtie2 index.
    """
    print('building bowtie index', file=sys.stderr)
    logfile = os.path.join(reference.paths['root'], 'bowtie2_log.txt')
    if os.path.isfile(logfile):
        os.remove(logfile)

    dna_path = reference.paths['dna']
    out_path = reference.paths['bowtieIndex']

    # Make output directory.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    args = ['bowtie2-build', dna_path, out_path, '--threads', nthreads]
    output = run_sys(args, prefix='bowtie2', file=logfile)

    # if execution comes here, the command ran successfully
    with open(logfile, 'a') as f:
        f.write('# success')

def build_kallisto(reference, nthreads=1):
    """
    Builds kallisto index.
    """
    print('building kallisto index', file=sys.stderr)
    logfile = os.path.join(reference.paths['root'], 'kallisto_log.txt')
    if os.path.isfile(logfile):
        os.remove(logfile)

    cdna_path = reference.paths['cdna']
    out_path = reference.paths['kallistoIndex']

    # Make output directory.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    args = ['kallisto', 'index', '-i', out_path, cdna_path]
    output = run_sys(args, prefix='kallisto', file=logfile)

    # if execution comes here, the command ran successfully
    with open(logfile, 'a') as f:
        f.write('# success')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Build indices.')
    parser.add_argument('objectId', type=str,
                        help='objectId of the reference for which to build '
                             + 'the index')
    args = parser.parse_args()
    objectId = args.objectId

    with configure_scope() as scope:
        scope.user = {'id': objectId}

        # Get number of threads.
        config = Config.get()
        nthreads = config['threads']


        # Get reference object.
        Reference = Object.factory('Reference')
        reference = Reference.Query.get(objectId=objectId)

        # Build bowtie2 index.
        build_bowtie2(reference, nthreads)

        # Build kallisto index.
        build_kallisto(reference, nthreads)

        # Success. This reference is ready to be used.
        reference.ready = True
        reference.save()
