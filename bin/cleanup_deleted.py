#!/usr/bin/env python
"""
Delete files from the filesystem and the database which have been deleted more than 72 hours ago
"""

import argparse
import datetime
import logging
import os
import sys

import pymongo

from flywheel_common import storage

from api import util
from api.site.storage_provider_service import StorageProviderService


log = logging.getLogger('cleanup_deleted')
cont_names = ['projects', 'subjects', 'sessions', 'acquisitions', 'analyses', 'collections']


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

    storage_service = StorageProviderService()
    local_fs = storage_service.determine_provider(None, None)
    fs = local_fs.storage_plugin

    db_uri = os.environ['SCITRAN_PERSISTENT_DB_URI']
    db = pymongo.MongoClient(db_uri).get_default_database()

    log.info('Using mongo URI: %s', db_uri)
    log.info('Using data provider: %s', local_fs.provider_id)
    log.info('Using storage path: %s', local_fs.storage_url)

    origins = []

    if args.job:
        origins.append('job')
    if args.reaper:
        origins.append('device')

    if not (args.all or origins):
        log.error('You have to specify at least one argument (--job, --reaper, --all)')
        exit(1)

    cleanup_files(args.all, origins)


def cleanup_files(remove_all, origins):
    log.info('Cleanup deleted container (projects, acquisitions, sessions, collections, analyses) files...')

    d = datetime.datetime.now() - datetime.timedelta(hours=72)

    for container in cont_names:
        log.info("Cleaning up %s" % container)

        cursor = db.get_collection(container).aggregate([
            {
                "$match": {
                    "$or": [
                        {"files.deleted": {"$lte": d}},
                        {"deleted": {"$lte": d}}
                    ]
                }
            },
            {
                "$project": {
                    "files": {
                        "$ifNull": [
                            {
                                "$filter": {
                                    "input": "$files",
                                    "as": "item",
                                    "cond": {
                                        "$or": [
                                            {
                                                "$and": [
                                                    # $lte return true if the deleted field not exists
                                                    {"$lte": ["$$item.deleted", d]},
                                                    {"$ifNull": ["$$item.deleted", False]}
                                                ]
                                            },
                                            {
                                                "$and": [
                                                    # $lte return true if the deleted field not exists
                                                    {"$lte": ["$deleted", d]},
                                                    {"$ifNull": ["$deleted", False]}
                                                ]
                                            }
                                        ]
                                    }
                                }
                            },
                            []
                        ]
                    },
                    "deleted": 1
                }
            }
        ])

        for document in cursor:
            for i, f in enumerate(document.get('files', [])):
                if not remove_all and f['origin']['type'] not in origins:
                    log.debug('  skipping %s/%s/%s since it was uploaded by %s',
                              container, document['_id'], f['name'], f['origin']['type'])
                    continue

                log.debug('  file marked to delete: %s, parent marked to delete: %s',
                          f.get('deleted', False),
                          document.get('deleted', False))
                log.debug('  removing %s/%s/%s', container, document['_id'], f['name'])

                if f.get('_id'):
                    uuid_path = util.path_from_uuid(f['_id'])
                    if fs.get_file_info(f['_id'], uuid_path):
                        log.debug('    removing from %s', fs)
                        fs.remove_file(f['_id'], uuid_path)

                    log.debug('    removing from database')
                    updated_doc = db.get_collection(container).update({'_id': document['_id']},
                                                                      {'$pull': {'files': {'_id': f['_id']}}})
                    if not updated_doc['nModified']:
                        log.error('    couldn\'t remove file from database')
                        exit(1)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--all', action='store_true', help='Cleanup everything including files uploaded by a user')
    parser.add_argument('--job', action='store_true', help='Cleanup files with job origin')
    parser.add_argument('--reaper', action='store_true', help='Cleanup files with reaper origin')
    parser.add_argument('--log-level', default='info', metavar='LEVEL', help='log level [info]')

    return parser.parse_args(argv)


if __name__ == '__main__':
    main()
