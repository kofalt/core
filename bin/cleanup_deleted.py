#!/usr/bin/env python
"""
Delete files from the filesystem and the database which have been deleted more than 72 hours ago
"""

import argparse
import datetime
import logging
import os
import bson
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
    elif args.project and not args.all:
        log.error('The project flag only works when deleting all files')
        exit(1)


    cleanup_files(args.all, origins, args.project, args.job_phi)


def execute_job_operations(job_operations, job_log_operations):
    """Unsets produced metadata and deletes job logs for the the jobs specified
    by the request list given

    Args:
        job_operations (list): A list of UpdateOne operations
        job_log_operations (list): A list of DeleteOne operations
    Returns:
        tuple: tuple of modified count and deleted count
    """
    # Make the bulk write operations
    if job_operations:
        log.debug('going to purge %s jobs of produced_metadata', len(job_operations))
        job_bulk_response = db.jobs.bulk_write(job_operations)
        modified_count = job_bulk_response.modified_count
    else:
        modified_count = 0
    if job_log_operations:
        log.debug('going to remove %s job logs', len(job_log_operations))
        job_log_bulk_response = db.job_logs.bulk_write(job_log_operations)
        deleted_count = job_log_bulk_response.deleted_count
    else:
        deleted_count = 0

    return modified_count, deleted_count


def generate_job_operations(container_list):
    """Find all jobs with destination of a specific container

    Args:
        container_list (list): list of ids of the destination containers
    Returns:
        tuple: A set of lists of operations to be executed on the database
    """
    jobs = db.jobs.find(
        {
            'destination.id': {
                '$in': [str(container_id) for container_id in container_list]
            }
        },
        {
            '_id': 1
        }
    )
    log.debug('Found %s jobs', jobs.count())
    job_operations = []
    job_log_operations = []
    for job in jobs:
        job_operations.append(pymongo.operations.UpdateOne(
            {'_id': job['_id']},
            {'$unset': {'produced_metadata': ''}}
        ))
        job_log_operations.append(pymongo.operations.DeleteOne(
            {'_id': str(job['_id'])}
        ))

    return job_operations, job_log_operations


def cleanup_files(remove_all, origins, project_id, job_phi):
    log.info('Cleanup deleted container (projects, acquisitions, sessions, collections, analyses) files...')

    deleted_date_cutoff = datetime.datetime.now() - datetime.timedelta(hours=72)
    container_ids = []

    for container in cont_names:
        log.info("Cleaning up %s" % container)

        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"files.deleted": {"$lte": deleted_date_cutoff}},
                        {"deleted": {"$lte": deleted_date_cutoff}}
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
                                                    {"$lte": ["$$item.deleted", deleted_date_cutoff]},
                                                    {"$ifNull": ["$$item.deleted", False]}
                                                ]
                                            },
                                            {
                                                "$and": [
                                                    # $lte return true if the deleted field not exists
                                                    {"$lte": ["$deleted", deleted_date_cutoff]},
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
        ]
        if project_id:
            # Use the id field or parents.project field to filter results
            # instead of date of deletion
            project_filter = {
                '$or': [
                    {'_id': bson.ObjectId(project_id)},
                    {'parents.project': bson.ObjectId(project_id)}
                ]
            }

            # We don't care about time of deletetion for single project snipes
            pipeline[0]['$match'].pop('$or')
            deleted_filter = {'$or': [
                {'files.deleted': {'$exists': True}},
                {'deleted': {'$exists': True}}
            ]}

            pipeline[0]['$match']['$and'] = [deleted_filter, project_filter]
            pipeline[1]['$project'] = {'files': 1, 'deleted': 1}

        cursor = db.get_collection(container).aggregate(pipeline)
        job_operations = []
        job_log_operations = []
        jobs_modified = 0
        job_logs_deleted = 0

        for document in cursor:
            document_deleted = False

            if project_id and job_phi:
                # Append the container id to the list to purge jobs of phi
                container_ids.append(document['_id'])
                if document.get('deleted'):
                    # if the document is deleted, remove it from the database
                    # since it might have phi from engine uploads
                    # NOTE: we only do this if job-phi is also set so that we can if needed,
                    # go back and delete the job phi
                    response = db.get_collection(container).delete_one({'_id': document['_id']})
                    document_deleted = response.deleted_count == 1

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

                    if not document_deleted:
                        # only need to remove the file from the database
                        # if the document wasn't already removed
                        log.debug('    removing from database')
                        update_result = db.get_collection(container).update_one({'_id': document['_id']},
                                                                                {'$pull': {'files': {'_id': f['_id']}}})
                        if not update_result.modified_count == 1:
                            log.error('    couldn\'t remove file from database')
                            exit(1)

            if len(container_ids) == 100:
                # Chunking the number of jobs to find to
                # Number of jobs from 100 containers
                job_operations, job_log_operations = generate_job_operations(container_ids)
                result = execute_job_operations(job_operations, job_log_operations)
                jobs_modified += result[0]
                job_logs_deleted += result[1]
                container_ids = []

    if container_ids:
        # find the jobs % 100 left
        job_operations, job_log_operations = generate_job_operations(container_ids)
        result = execute_job_operations(job_operations, job_log_operations)
        jobs_modified += result[0]
        job_logs_deleted += result[1]
        container_ids = []
    log.debug('Purged phi from %s, and removed %s jobs logs', jobs_modified, job_logs_deleted)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--all', action='store_true', help='Cleanup everything including files uploaded by a user')
    parser.add_argument('--job', action='store_true', help='Cleanup files with job origin')
    parser.add_argument('--reaper', action='store_true', help='Cleanup files with reaper origin')
    parser.add_argument('--log-level', default='info', metavar='LEVEL', help='log level [info]')
    parser.add_argument('--project', help='Id of a deleted project to limit the clean up to. This will delete file regardless of deletion time')
    parser.add_argument('--job-phi', action='store_true', help='Cleanup jobs by remove logs and produced metadata')

    return parser.parse_args(argv)


if __name__ == '__main__':
    main()
