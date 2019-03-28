"""Provide Bulk downloads (via list of file references)"""
import os
import bson

from ... import config, files
from ...dao import containerutil
from ...web import errors
from .. import models
from .abstract import AbstractDownloadStrategy

class BulkDownloadStrategy(AbstractDownloadStrategy):
    default_archive_prefix = 'scitran'

    supported_containers = ['project', 'subject', 'session', 'acquisition', 'analysis']

    def validate_spec(self, spec, summary):
        # Legacy Bulk Download had no previous validation
        for fref in spec.get('files', []):
            cont_name   = fref.get('container_name','')
            self.log.info('validate: %s', cont_name)
            if cont_name not in self.supported_containers:
                raise errors.InputValidationException('Bulk download only supports files in projects, subjects, sessions, analyses and acquisitions')

    def identify_targets(self, spec, uid, summary):
        # Legacy Bulk Download by list of file references
        # Did not check for deleted files before, nor does it now
        for fref in spec.get('files', []):
            cont_id     = fref.get('container_id', '')
            filename    = fref.get('filename', '')
            cont_name   = fref['container_name']
            coll_name   = containerutil.pluralize(cont_name)

            file_obj = None
            try:
                # Try to find the file reference in the database (filtering on user permissions)
                query = {'_id': bson.ObjectId(cont_id)}
                if uid is not None:
                    query['permissions._id'] = uid
                file_obj = config.db[coll_name].find_one(
                    query,
                    {'files': { '$elemMatch': {
                        'name': filename
                    }}
                })['files'][0]
            except Exception: # pylint: disable=broad-except
                self.log.warn('Expected file {} on Container {} {} to exist but it is missing. File will be skipped in download.'.format(filename, cont_name, cont_id))
                continue

            src_path = files.get_file_path(file_obj)
            if src_path:  # silently skip missing files
                dst_path = os.path.join(cont_name, cont_id, file_obj['name'])
                yield models.DownloadTarget('file', dst_path, cont_name, cont_id, file_obj['modified'],
                    file_obj['size'], file_obj.get('type'), file_id=file_obj.get('_id'),
                    filename=file_obj['name'], src_path=src_path)
            else:
                self.log.debug('Could not resolve path for file {} on {} {}. File will be skipped in download.'.format(filename, cont_name, cont_id))
