""" Provides the local PyFs Storage Provider """
from marshmallow import Schema, fields
import uuid

from flywheel_common.providers.storage.base import BaseStorageProvider
from flywheel_common.providers.provider import BaseProviderSchema
from flywheel_common import errors
from api.config import log

class LocalStorageConfigSchema(Schema):
    # Is blank a valid path?  Root??
    path = fields.String(required=True, allow_none=False, allow_blank=True)

class LocalStorageProviderSchema(BaseProviderSchema):
    """Schema definition for the object"""
    config = fields.Nested(LocalStorageConfigSchema, many=False, required=True)
    creds = fields.Dict(required=False, allow_none=True, allow_blank=True)


# pylint: disable=too-few-public-methods
class LocalStorageProvider(BaseStorageProvider):
    """The Local PyFS Storage provider object."""

    _schema = LocalStorageProviderSchema()
    _storage_plugin_type = 'osfs'

    def validate_permissions(self):
        #self._test_files()
        return True

    def get_redacted_config(self):
        return {
            'id': self.provider_id,
            'path': self.config.get('path'),
        }

    def _test_files(self):
        """
            Use the provider to upload to the path
        """

        test_uuid = str(uuid.uuid4())

        try:
            test_file = self._storage_plugin.open(test_uuid, 'wb')
            test_file.write('This is a permissions test')
            test_file.close()
        except:
            log.debug('Provider Error: Unable to write files to the local path')
            raise errors.PermissionError('Unable to write files to the local path')

        try:
            test_file = self._storage_plugin.open(test_uuid, 'rb')
            test_file.read()
            test_file.close()
        except:
            log.debug('Provider Error: Unable to read files on the local path')
            raise errors.PermissionError('Unable to read file on the local path')

        try:
            self._storage_plugin.remove_file(test_uuid)
        except:
            log.debug('Provider Error: Unable to remove files to the local path')
            raise errors.PermissionError('Unable to remove files on the local path')
