""" Provides the local PyFs Storage Provider """
import datetime
import hashlib
import hmac
import requests
import uuid

from flywheel_common.storage import create_flywheel_fs
from ...web import errors
from .factory import ProviderKey
from ..models import ProviderClass
from .base import BaseProvider

# pylint: disable=too-few-public-methods
class LocalStorageProvider(BaseProvider):
    """The Local PyFS Storage provider object."""

    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(ProviderClass.storage, 'osfs')

    def __init__(self, config):

        super(LocalStorageProvider, self).__init__(config)

        self._storage_plugin = None
        #self.validate_config()
    
        # URL used to instantiate the storage plugin provider
        # We assume its a valid absolute url with leading /
        # we should verify this on the settings config page
        self._storage_url = "osfs://" + self.config.get('path', '')
        self._storage_plugin = create_flywheel_fs(self._storage_url)


    def validate_config(self):
        """
            Confirms the minimum required config is set
        """

        if not self.config:
            raise errors.APIValidationException('Local storage configuration is required')

        if not self.config.get('path'):
            raise errors.APIValidationException('Local Storage requires path be set')

        # We need to have a valid storage object set to run these
        if self._storage_plugin:
            pass
            #self._validate_permissions()
            #self._test_files()
    
    def get_redacted_config(self):
        return {
            'id': self.provider_id,
            'path': self.config.get('path'),
        }

    def _validate_permissions(self):
        """
            Do a permission check on the files to be sure we can write files at the path
        """
        # TODO: make this correct
        self._test_files()
        return True

    def _test_files(self):
        """
            Use the provider to upload to the path 
        """

        test_uuid = str(uuid.uuid4())

        # TODO wrap these in try blocks and catch the errors as we go
        test_file = self._storage_plugin.open(test_uuid, 'wb')
        test_file.write('This is a permissions test')
        test_file.close()

        test_file = self._storage_plugin.open(test_uuid, 'rb')
        test_file.read()
        test_file.close()

        self._storage_plugin.remove_file(test_uuid)

    @property
    def storage_url(self):
        """
            Allow access to the internal storage url
            This will not be needed once the url is removed from the storage factory
        """
        return self._storage_url

    @property
    def storage_plugin(self):
        """
            Allow access to the internal storage url
            This will not be needed once the url is removed from the storage factory
        """
        return self._storage_plugin
