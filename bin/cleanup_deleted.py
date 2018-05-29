#!/usr/bin/env python

import argparse
import datetime
import logging
import os
import sys

import pymongo

from fs import open_fs

from api import util


log = logging.getLogger('cleanup_deleted')
cont_names = ['projects', 'sessions', 'acquisitions', 'analyses', 'collections']


def main(*argv):
    argv = argv or sys.argv[1:]
    args = parse_args(argv)

    date_format = '%Y-%m-%d %H:%M:%S'
    log_format = '%(asctime)s %(levelname)6.6s %(message)s'
    logging.basicConfig(datefmt=date_format,
                        format=log_format,
                        level=getattr(logging, args.log_level.upper()))

    logging.getLogger('urllib3').setLevel(logging.WARNING)  # silence urllib3 library
    logging.getLogger('boto3').setLevel(logging.WARNING)  # silence boto3 library
    logging.getLogger('botocore').setLevel(logging.WARNING)  # silence botocore library
    logging.getLogger('azure.storage').setLevel(logging.WARNING)  # silence azure.storage library

    global db, fs, data_path
    db_uri = os.environ['SCITRAN_PERSISTENT_DB_URI']
    data_path = os.environ['SCITRAN_PERSISTENT_DATA_PATH']
    db = pymongo.MongoClient(db_uri).get_default_database()
    fs_url = os.environ['SCITRAN_PERSISTENT_FS_URL']
    fs = open_fs(fs_url)

    log.info('Using mongo URI: %s', db_uri)
    log.info('Using data path: %s', data_path)
    log.info('Using filesystem: %s', fs_url)

    cleanup_files(args.include_user_uploads)


def cleanup_files(remove_all=False):
    log.info('Cleanup deleted container (projects, acquisitions, sessions, subject, collections) files...')

    d = datetime.datetime.now() - datetime.timedelta(hours=72)

    for container in cont_names:
        cursor = db.get_collection(container).find({'files.deleted': {'$lte': d}},
                                                   {'files': {'$elemMatch': {'deleted': {'$lte': d}}}})

        if not cursor.count():
            log.info('Nothing to remove from %s', container)

        for document in cursor:
            for i, f in enumerate(document['files']):
                if not remove_all and f['origin']['type'] == 'user':
                    log.debug('  skipping %s/%s/%s since it was uploaded by a user',
                              container, document['_id'], f['name'])
                    continue

                log.debug('  removing %s/%s/%s', container, document['_id'], f['name'])

                if f.get('_id'):
                    uuid_path = util.path_from_uuid(f['_id'])
                    if fs.exists(uuid_path):
                        log.debug('    removing from %s', fs)
                        fs.remove(uuid_path)

                    log.debug('    removing from database')
                    updated_doc = db.get_collection(container).update({'_id': document['_id']},
                                                                      {'$pull': {'files': f}})
                    if not updated_doc:
                        log.error('    couldn\'t remove file from database')
                        exit(1)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--include-user-uploads', action='store_true', help='Cleanup everything including files uploaded by a user')
    parser.add_argument('--log-level', default='info', metavar='LEVEL', help='log level [info]')

    return parser.parse_args(argv)


if __name__ == '__main__':
    main()
