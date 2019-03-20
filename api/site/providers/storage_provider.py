"""Provides the StorageProvider base class"""
from .provider_metaclass import ProviderMetaclass
from abc import abstractmethod
from .base import BaseProvider

#TODO: This class is not needed anymore as theStorage providers inherit directly from baseProvider now


# pylint: disable=too-few-public-methods
class StorageProvider(BaseProvider):
    """The storage provider object. Provides configuration and validation for storage resources"""
    # For automatic plugin registration
    __metaclass__ = ProviderMetaclass

    # Must set provider_key as (provider_class, provider_type)
    provider_key = None


    def __init__(self, config):
        """Initializes this class with the given configuration

        Args:
            config (dict): The configuration object
        """
        self._storage_url = None
        self._storage_plugin = None

        self.config = config

    @property
    def storage_plugin(self):
        """ returns the current storage plugin. Only needed until IoC is refactored """
        return self._storage_plugin

    @storage_plugin.setter
    def storage_plugin(self, value):
        """
            Allow setting the storage plugin.
            This should be moved to the constructor once we refacter the storage URL
        """
        self._storage_plugin = value

    @abstractmethod
    def validate_config(self):
        """Perform the necessary steps to validate the given configuration.

        This should include (but not be limited to):
            - Validating the credentials
            - Validating that required permissions are present
            - Validating that the credentials do not have EXCESSIVE permissions

        Raises:
            APIValidationException: If the credentials appear to be invalid
        """
        pass
