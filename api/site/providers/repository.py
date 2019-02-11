"""Provides repository-layer functions for loading/saving providers"""
from ...web import errors
from .factory import create_provider
from ..mappers import ProviderMapper


def get_provider(provider_id):
    """Get the provider document matching provider_id, or None if not found.

    Args:
        provider_id (str): The provider id

    Returns:
        The provider document (without config)

    Raises:
        APINotFoundException: If the provider does not exist.
    """
    mapper = ProviderMapper()
    result = mapper.find(provider_id)
    if not result:
        raise errors.APINotFoundException('Provider {} not found!'.format(provider_id))
    return _scrub_config(result)


def get_provider_config(provider_id):
    """Get the provider configuration matching provider_id, or None if not found.

    Args:
        provider_id (str): The provider id

    Returns:
        The provider configuration

    Raises:
        APINotFoundException: If the provider does not exist.
    """
    mapper = ProviderMapper()
    result = mapper.find(provider_id)
    if not result:
        raise errors.APINotFoundException('Provider {} not found!'.format(provider_id))
    return result.config


def get_providers_by_class(provider_class):
    """Get all providers matching the given type, without config.

    Args:
        provider_class (ProviderClass|str): The provider class

    Yields:
        Provider: The next provider matching the given class
    """
    mapper = ProviderMapper()
    for provider in mapper.find_by_class(provider_class):
        yield _scrub_config(provider)


def insert_provider(provider):
    """Insert the given provider into the database.

    Args:
        provider (Provider): The provider model.

    Returns:
        ObjectId: The inserted provider id

    Raises:
        APIValidationException: If an invalid provider type is specified,
            or if the given configuration is invalid.
    """
    try:
        # Try to create a provider of the given type
        provider_inst = create_provider(provider.provider_class,
            provider.provider_type, provider.config)

        # Then validation the configuration
        provider_inst.validate_config()
    except ValueError as e:
        # Re-raise as ValidationException
        raise errors.APIValidationException(str(e))

    # All was good, create the mapper and insert
    mapper = ProviderMapper()
    return mapper.insert(provider)


def update_provider(provider_id, doc):
    """Update the given provider instance, with fields from doc.

    Args:
        provider_id (ObjectId|str): The provider id
        doc (dict): The update fields

    Raises:
        APINotFoundException: If the provider does not exist.
        InputValidationException: If an invalid property was specified
        APIValidationException: If the update would result in
            an invalid provider configuration.
    """
    mapper = ProviderMapper()
    current_provider = mapper.find(provider_id)

    if not current_provider:
        raise errors.APINotFoundException('Provider {} not found!'.format(provider_id))

    # NOTE: We do NOT permit updating provider class or type
    if 'provider_class' in doc:
        raise errors.InputValidationException('Cannot change provider class!')

    if 'provider_type' in doc:
        raise errors.InputValidationException('Cannot change provider type!')

    if 'config' in doc:
        # Validate the new configuration
        provider_inst = create_provider(current_provider.provider_class,
            current_provider.provider_type, doc['config'])
        provider_inst.validate_config()

    mapper.patch(provider_id, doc)


def _scrub_config(provider):
    """Remove config attribute from provider model

    Args:
        provider (Provider): The provider model

    Returns:
        Provider: The provider that was passed in"""
    if provider is not None:
        del provider.config
    return provider
