"""Provides repository-layer functions for loading/saving providers"""
import datetime
import bson

from flywheel_common.providers import ProviderClass, create_provider
from flywheel_common import errors

from ... import config
from .. import mappers, multiproject


COMPUTE_DISPATCHERS = [ 'cloud-scale', 'compute-dispatcher' ]

def is_compute_dispatcher(device_type):
    """Whether or not the given device_type is a compute dispatcher"""
    return device_type in COMPUTE_DISPATCHERS


def get_provider(provider_id, secure=False):
    """Get the provider model matching provider_id, or None if not found.

    Args:
        provider_id (str): The provider id

    Returns:
        The provider object (without config)

    Raises:
        APINotFoundException: If the provider does not exist.
    """
    mapper = mappers.Providers()
    result = mapper.get(provider_id)
    if not result:
        raise errors.ResourceNotFound(provider_id, 'Provider {} not found!')
    if not secure:
        return _scrub_config(result)
    return result

def validate_provider_class(provider_id, provider_class):
    """Validate that the given provider exists, and has the given class.

    Args:
        provider_id (str): The provider id
        provider_class (str|ProviderClass): The provider class

    Raises:
        APIValidationException: If the provider either doesn't exist or is not of the specified class.
    """
    provider_class = ProviderClass(provider_class).value
    mapper = mappers.Providers()
    result = mapper.get(provider_id)

    if not result:
        raise errors.ResourceNotFound(provider_id, 'Provider {} does not exist')
    if result.provider_class != provider_class:
        raise errors.ValidationError('Provider {} is not a {} provider!'.format(
            provider_id, provider_class.value))

def get_provider_config(provider_id, full=False):
    """Get the provider configuration matching provider_id, or None if not found.

    Args:
        provider_id (str): The provider id
        full (bool): Whether or not to include confidential fields

    Returns:
        The provider configuration

    Raises:
        ResourceNotFound: If the provider does not exist.
    """
    mapper = mappers.Providers()
    result = mapper.get(provider_id)
    if not result:
        raise errors.ResourceNotFound(provider_id, 'Provider {} not found!')

    if full:
        # Cannot get storage provider config this way
        if result.provider_class != ProviderClass.compute.value:
            raise errors.PermissionError('Storage config', 'Only compute config can be retrieved with this method')
        return result.config

    return result.get_redacted_config()


def get_providers(provider_class=None, secure=False):
    """Get all providers matching the given type, without config.

    Args:
        provider_class (ProviderClass|str): The provider class, if filtering is desired

    Yields:
        Provider: The next provider matching the given class
    """
    mapper = mappers.Providers()
    for provider in mapper.find_all(provider_class):
        if not secure:
            yield _scrub_config(provider)
        else:
            yield provider


def insert_provider(provider):
    """Insert the given provider into the database.

    Args:
        provider (Provider): The provider model.

    Returns:
        ObjectId: The inserted provider id

    Raises:
        ValueError: If an invalid provider type is specified
    """

    # We validate in case the provider was created outside our create_provider method.
    values = set(item.value for item in ProviderClass)
    if not provider.provider_class in values:
        raise errors.ValidationError('Unregistered provider class specified')

    provider.created = datetime.datetime.utcnow()
    provider.modified = datetime.datetime.utcnow()

    provider.validate()
    provider.validate_permissions()
    # All was good, create the mapper and insert, errors will bubble up
    mapper = mappers.Providers()
    return mapper.insert(provider)


def update_provider(provider_id, doc):
    """Update the given provider instance, with fields from doc.

    Args:
        provider_id (ObjectId|str): The provider id
        doc (dict): The update fields

    Raises:
        APINotFoundException: If the provider does not exist.
        APIValidationException: If the update would result in an invalid provider
            configuration, or an invalid field was specified
            (e.g. attempt to change provider type)
    """
    mapper = mappers.Providers()
    current_provider = mapper.get(provider_id)

    if not current_provider:
        raise errors.ResourceNotFound(provider_id, 'Provider {} not found!')

    # NOTE: We do NOT permit updating provider class or type
    if 'provider_class' in doc:
        raise errors.ValidationError('Cannot change provider class!')

    if 'provider_type' in doc:
        raise errors.ValidationError('Cannot change provider type!')

    if 'label' in doc:
        current_provider.label = doc['label']
    # If we do it this way we can only ever update keys not delete them
    if 'config' in doc:
        current_provider.config = doc['config']
        #for key in doc['config']:
        #    current_provider.config[key] = doc['config'][key]
    current_provider.modifed = datetime.datetime.utcnow()
    current_provider.validate()

    if 'creds' in doc:
        # Do full validation if the creds are changed to confirm they are correct
        provider = create_provider(current_provider.provider_class,
                current_provider.provider_type, current_provider.label,
                current_provider.config, doc['creds'], provider_id)
        provider.validate_permissions()

    mapper.patch(provider_id, current_provider)


def validate_provider_updates(container, provider_ids, is_admin):
    """Validate an update (or setting) of provider ids.

    Allows setting or changing a compute provider on the container as long
    as the user is an admin and the provider exists.

    Allows setting the storage provider on the container as long as:
    1. The user is admin
    2. The provider exists
    3. A storage provider isn't already set

    Setting either provider to the current value is a no-op and doesn't
    trigger authorization errors.

    Side-effect: This will convert any IDs in the provider_ids parameter to ObjectIds.

    Args:
        container (dict): The current container (or empty if it doesn't exist)
        provider_ids (dict): The provider ids to update.
        is_admin (bool): Whether or not the user is a site administrator

    Raises:
        APIPermissionException: If the user is unautorized to make the change.
        APIValidationException: If the user attempted an invalid transition.
        APINotFoundException: If the given storage provider does not exist.
    """
    # Early return for empty provider_ids object
    if not provider_ids:
        return

    # First check if this is a change
    updates = {}
    current_provider_ids = container.get('providers') or {}

    for provider_class in ('compute', 'storage'):
        updates[provider_class] = False
        if provider_class in provider_ids:
            # Ensure ObjectId
            provider_ids[provider_class] = bson.ObjectId(provider_ids[provider_class])
            current_id = current_provider_ids.get(provider_class)
            if current_id != provider_ids[provider_class]:
                if current_id:
                    raise errors.ValidationError('Cannot change {} provider once set!'.format(provider_class))

                updates[provider_class] = True

    # Verify that the user is admin
    if (updates['storage'] or updates['compute']) and not is_admin:
        raise errors.PermissionError('site admin', 'Changing providers requires site-admin!')

    # Verify that provider exists and is the correct type
    for provider_class in ('compute', 'storage'):
        if not updates[provider_class]:
            continue
        provider = get_provider(provider_ids[provider_class])

        if provider.provider_class != ProviderClass(provider_class).value:
            raise errors.ValidationError(provider.provider_class, 'Invalid provider class: {}')


def get_provider_id_for_container(container, provider_class, site_settings=None):
    """Get the effective provider of type provider_class for the given container.

    Walks up the tree, as needed, stopping at site to determine the provider.

    Args:
        container (dict): The container under question.
        provider_class (ProviderClass|str): The class of provider to retrieve.
        site_settings (SiteSettings): Optional site_settings, if preloaded

    Returns:
        (bool, ObjectId): True if this is a site provider, and the provider id, if found, otherwise None
    """
    picker = _get_provider_picker()
    return picker.get_provider_id_for_container(container, provider_class, site_settings=site_settings)


def get_compute_provider_id_for_job(gear, destination, inputs):
    """Determine the compute provider for the given job profile.

    Args:
        gear (dict): The resolved gear document
        destination (dict): The destination container
        inputs (list(dict)): The list of input containers, with origins

    Returns:
        ObjectId: The id of the provider, or None if no applicable provider was found.

    Raises:
        APIValidationException: If invalid args were passed
    """
    picker = _get_provider_picker()
    return picker.get_compute_provider_id_for_job(gear, destination, inputs)


def _get_provider_picker():
    """Get the configured provider picker"""
    return multiproject.create_provider_picker(config.is_multiproject_enabled())


def _scrub_config(provider):
    """Remove creds attribute from provider model

    Args:
        provider (Provider): The provider model

    Returns:
        Provider: The provider that was passed in"""
    if provider is not None:
        del provider.creds
    return provider
