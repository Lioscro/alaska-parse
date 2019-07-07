import os
import ftplib

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

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

def upload(project, host, username, password, fname):
    print('uploading project {}'.format(project.objectId))
    archive_path = project.files['geo']
    geo_dir = Config.get()['geoDir']

    # Open a new FTP connection.
    try:
        with ftplib.FTP(host, username, password) as conn:
            conn.cwd(geo_dir)

            with open(archive_path, 'rb') as f:
                conn.storbinary('STOR {}'.format(fname), f)
    except Exception as e:
        raise Exception('error occured while uploading {}'.format(project.objectId))

def run_upload(objectId, host, username, password, geo_username):
    # Get project with specified objectId.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    upload(project, host, username, password, '{}_files.tar.gz'.format(geo_username))

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Perform post.')
    parser.add_argument('objectId', type=str)
    parser.add_argument('host', type=str)
    parser.add_argument('username', type=str)
    parser.add_argument('password', type=str)
    parser.add_argument('geo_username', type=str)
    args = parser.parse_args()

    objectId = args.objectId
    host = args.host
    username = args.username
    password = args.password
    geo_username = args.geo_username

    # Get project with specified objectId.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    upload(project, host, username, password, '{}_files.tar.gz'.format(geo_username))
