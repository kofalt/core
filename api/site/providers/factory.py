"""Provides registration and factory methods for provider classes"""
import collections

# Lookup key for provider classes
#     provider_class (ProviderClass): The provider class (compute or storage)
#     provider_type (str): A provider type string
ProviderKey = collections.namedtuple("ProviderKey", ["provider_class", "provider_type"])

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
        raise ValueError("Unknown provider: {}".format(key))

    return cls(config)
