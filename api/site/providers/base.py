"""Provides the BaseProvider base class"""
from .provider_metaclass import ProviderMetaclass
from abc import abstractmethod


class BaseProvider(object):
    """The compute provider object. Provides configuration and validation for compute resources"""

    # For automatic plugin registration
    __metaclass__ = ProviderMetaclass

    # Must set provider_key as (provider_class, provider_type)
    provider_key = None

    def __init__(self, config):
        """Initializes this class with the given configuration

        Args:
            config (dict): The configuration object
        """
        self.config = config

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

    @abstractmethod
    def get_redacted_config(self):
        """Return the configuration with all private key material and credentials replaced with None.

        This function can be used to retrieve scrubbed configuration, with only non-confidential
        fields populated.

        Args:
            placeholder: The placeholder for redacted fields.

        Returns:
            dict: The non-confidential configuration
        """
