#!/usr/bin/env python
"""
Migrate storage backend from one Provider to anohter Provider
"""

import argparse
import datetime
import logging
import os
import time
import uuid
import sys
import pymongo
from functools import wraps

from fs import errors


from flywheel_common import storage
from api import util
from api.site.providers import get_provider

CHUNK_SIZE = 2 ** 20

log = logging.getLogger('migrate_storage')

def main(*argv):
    """
    Supports moving files from one provider to another provider via provider_id
    """
    argv = argv or sys.argv[1:]
    args = parse_args(argv)

    date_format = '%Y-%m-%d %H:%M:%S'
    log_format = '%(asctime)s %(levelname)4.4s %(message)s'
    logging.basicConfig(datefmt=date_format,
                        format=log_format,
                        level=getattr(logging, args.log_level.upper()))

    global db, target_fs, migrate_file, sources, dest_storage, delete_source, filter_source
    db_uri = os.environ['SCITRAN_PERSISTENT_DB_URI']
    log.info('Using mongo URI: %s', db_uri)
    db = pymongo.MongoClient(db_uri).get_default_database()

    sources = {}; #Just so we dont have to keep loading all the source types
    try:
        dest_storage = get_provider(args.destination)
    except: 
        log.error('Unable to locate the destination provider specifed. Be sure this provider exists in the system')
        exit(1)

    log.info('Migrate files to %s', dest_storage.label)
    
    target_fs = dest_storage.storage_plugin
    delete_source = False
    if args.delete_files:
        log.info('Deleting source files')
        delete_source = True;

    filter_source = None
    if args.source:
        filter_source = args.source
        log.info("Only moving filters from provider with id %s", filter_source) 

    try:
        if not (args.containers or args.gears):
            migrate_containers()
            migrate_gears()

        if args.containers:
            migrate_containers()

        if args.gears:
            migrate_gears()

    except MigrationError:
        log.critical('Migration failed')
        exit(1)

    log.info('Migration completed successfully')


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--destination', required=True, help='Destination Provider Id')
    parser.add_argument('--source', help='Only move files from this Provider Id')
    parser.add_argument('--containers', action='store_true', help='Migrate containers')
    parser.add_argument('--gears', action='store_true', help='Migrate gears')
    parser.add_argument('--delete-files', action='store_true', help='Delete files from source storage provider')
    parser.add_argument('--log-level', default='info', metavar='PATH', help='log level [info]')

    return parser.parse_args(argv)


def get_files_by_prefix(document, prefix):
    for key in prefix.split('.'):
        document = document.get(key, {})
    return document


def show_progress(current_index, total_files):
    if current_index % (total_files / 10 + 1) == 0:
        log.info('Processed %s files of total %s files ...' % (current_index, total_files))

def get_containers_files(containers_prefixes):
    _files = []

    for container, prefix in containers_prefixes:
        cursor = db.get_collection(container).find({})
        for document in cursor:
            for f in get_files_by_prefix(document, prefix):
                f_dict = {
                    'container_id': document.get('_id'),
                    'container': container,
                    'fileinfo': f,
                    'prefix': prefix
                }

                if filter_source and f.provider_id != filter_source:
                    continue

                _files.append(f_dict)

    return _files


def get_gears_files():
    cursor = db.get_collection('gears').find({})
    _files = []

    for document in cursor:
        if document.get('exchange', {}).get('git-commit', '') == 'local':
            f_dict = {
                'gear_id': document['_id'],
                'gear_name': document['gear']['name'],
                'exchange': document['exchange']
            }

            if filter_source and document['exchange']['rootfs-provider-id'] != filter_source:
                continue

            _files.append(f_dict)

    return _files


def retry(exception_to_check, tries=4, delay=3, backoff=2):
    """Retry calling the decorated function using an exponential backoff.

    :param exception_to_check: the exception to check. may be a tuple of
        exceptions to check
    :type exception_to_check: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    """

    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exception_to_check:
                    f_to_migrate = args[0]
                    msg = "Couldn't upload %s/%s/%s to target storage, retrying in %ds (%s)..." % \
                          (f_to_migrate['container'], f_to_migrate['container_id'], f_to_migrate['fileinfo']['name'], mdelay, tries-mtries+1)
                    log.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            try:
                return f(*args, **kwargs)
            except exception_to_check as e:
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    log.error(e.response.text)
                raise MigrationError

        return f_retry

    return deco_retry


def migrate_file(f):

    source_fs = get_source_fs(f['fileinfo']['provider_id'])

    file_id = f['fileinfo']['_id']
    with source_fs.open(file_id, None, 'rb') as (f1
            ), target_fs.open(file_id, None, 'wb') as f2:
        while True:
            data = f1.read(CHUNK_SIZE)
            if not data:
                break
            f2.write(data)

    # We update first in case there are any issues with delete. 
    db[f['container']].find_one_and_update(
            {'_id': f['container_id'], 'files._id': file_id},
            {'$set': {'files.$.provider_id': dest_storage.provider_id}})

    if delete_source:
        source_fs.remove_file(file_id, None)   

def migrate_analysis_file(f):

        file_id = f['fileinfo']['_id']
        source_fs = get_source_fs(f['fileinfo']['provider_id'])

        with source_fs.open(file_id, None, 'rb') as (f1
                ), target_fs.open(file_id, None, 'wb') as f2:
            while True:
                data = f1.read(CHUNK_SIZE)
                if not data:
                    break
                f2.write(data)
        # Update provider in the db
        db[f['container']].find_one_and_update(
                {'_id': f['container_id'], 'inputs._id': file_id},
                {'$set': {'inputs.$.provider_id': dest_storage.provider_id}})


def migrate_containers():
    log.info('Migrate container (project/subject/session/acquisition/collection) files...')

    container_files = get_containers_files([('projects', 'files'),
                                            ('acquisitions', 'files'),
                                            ('sessions', 'files'),
                                            ('subjects', 'files'),
                                            ('collections', 'files'),
                                            ('analyses', 'files')])

    for i, f in enumerate(container_files):
        log.debug('  [%s/%s] %s/%s/%s', i+1, len(container_files), f['container'], f['container_id'],
                  f['fileinfo']['name'])
        migrate_file(f)
        show_progress(i + 1, len(container_files))

    log.info('Migrate analysis files...')
    analysis_files = get_containers_files([('analyses', 'inputs')])

    for i, f in enumerate(analysis_files):
        log.debug('  [%s/%s] %s/%s/%s - %s', i+1, len(container_files), f['container'], f['container_id'],
                  f['fileinfo']['name'], f['fileinfo']['provider_id'])
        migrate_analysis_file(f)
        show_progress(i + 1, len(analysis_files))


def migrate_gear_files(f):
    file_id = f['exchange'].get('rootfs-id', '')
    source_fs = get_source_fs(f['exchange']['rootfs-provider-id'])
    
    with source_fs.open(file_id, None, 'rb') as (f1
            ), target_fs.open(file_id, None, 'wb') as f2:
        while True:
            data = f1.read(CHUNK_SIZE)
            if not data:
                break
            f2.write(data)
    
    db.gears.find_one_and_update(
            {'_id': f['gear_id']},
            {'$set': {'exchange.rootfs-provider-id': dest_storage.provider_id}})

    if delete_source:
        source_fs.remove_file(file_id)


def migrate_gears():
    log.info('Migrate gears...')

    _files = get_gears_files()

    for i, f in enumerate(_files):
        log.debug('  [%s/%s] gears/%s/%s', i+1, len(_files), f['gear_id'], f['gear_name'])
        migrate_gear_files(f)
        show_progress(i + 1, len(_files))

def get_source_fs(provider_id): 
    if not sources.get('provider_id'):
        sources[provider_id] = get_provider(provider_id)

    return sources[provider_id].storage_plugin

class MigrationError(Exception):
    pass


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log.critical('Unhandled exception', exc_info=True)
        exit(1)
    exit(0)
