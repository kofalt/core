"""Provides registration and factory methods for provider classes"""
import collections

from flywheel_common import create_flywheel_fs
from ..models.provider import ProviderClass

# Lookup key for provider classes
#     provider_class (ProviderClass): The provider class (compute or storage)
#     provider_type (str): A provider type string
ProviderKey = collections.namedtuple('ProviderKey',
    ['provider_class', 'provider_type'])

# Association of providers:
# Keys: ProviderKey
# Values: Class
PROVIDERS = {}

def create_provider(provider_class, provider_type, config):
    """Create a new provider instance.

    Args:
        provider_class (ProviderClass): The provider class (compute or storage)
        provider_type (str): The provider type string
        config (dict): The configuration dictionary for the provider

    Returns:
        object: The provider instance, if created

    Raises:
        ValueError: If the given provider class and type did not resolve to a class
    """
    key = ProviderKey(provider_class, provider_type)

    cls = PROVIDERS.get(key)
    if cls is None:
        raise ValueError('Unknown provider: {}'.format(key))

    provider = cls(config)

    if provider_class == ProviderClass.storage:
        # TOOO: we have some tight coupling because our storage factory parses the url to determine the type
        # So we need the url which is constructed in the provider internally.  We should convert the storage
        # factory to return the plugin based on provider class then the provider will init the plugin with 
        # the correct url. That will still allow completely decoupled testing 
        provider.storage_plugin = create_flywheel_fs(provider.storage_url)

    return cls(config)
