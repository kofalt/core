#!/usr/bin/env python
"""
Reinitialize the storage provider from the fs_persistent_url value.
"""
import datetime
import logging
import sys
import os

from flywheel_common.providers import ProviderClass, create_provider
from flywheel_common.storage import parse_storage_url

from api.site.providers.repository import validate_provider_class
from api.config import db

log = logging.getLogger('site_provider_override')


def main(*argv):

    date_format = '%Y-%m-%d %H:%M:%S'
    log_format = '%(asctime)s %(levelname)6.6s %(message)s'
    logging.basicConfig(datefmt=date_format,
                        format=log_format,
                        level='info')

    if not os.environ.get('SCITRAN_PERSISTENT_FS_URL'):
        log.error('You must have a SCITRAN_PERSISTENT_FS_URL environment variable defined')
        exit(1)

    scheme, bucket_name, path, params = parse_storage_url(os.environ['SCITRAN_PERSISTENT_FS_URL'])

    if scheme == 's3':
        config_ = {
            'bucket': bucket_name,
            'path': path,
            'region': params.get('region', None)
        }

        creds = {
            # IF these are not found the error will happen in create_provider
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY')
        }
        type_ = 'aws'
    elif scheme == 'gc':
        # GC uses gcs_key path
        creds = None
        config_ = {"path": os.environ['SCITRAN_PERSISTENT_FS_URL']}
        type_ = 'gc'

    else:
        # Local is a special case that uses no creds
        config_ = {"path": os.environ['SCITRAN_PERSISTENT_FS_URL']}
        creds = None
        type_ = 'local'

    # Create a provider for a quick sanity check to verify the values in the env var work
    _ = create_provider(ProviderClass.storage.value, type_, 'Primary Provider', config_, creds)

    storage = db.providers.insert_one({
        "origin": {"type": "system", "id": "system"},
        "created": datetime.datetime.now(),
        "config": config_,
        "creds": creds,
        "modified": datetime.datetime.now(),
        "label":"Primary Storage",
        "provider_class":"storage",
        "provider_type": type_
    })

    # We know its storage becase we just made it that way
    # validate_provider_class(args.storage, ProviderClass.storage.value)
    log.info('Setting storage provider: %s', storage.inserted_id)
    update = {'$set': {'providers.storage': storage.inserted_id}}
    db.singletons.update({'_id': 'site'}, update)
    log.info('Providers have been modified')


if __name__ == '__main__':
    main()
