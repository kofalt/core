"""Provides repository-layer functions for loading/saving providers"""
import bson

from ... import config
from ...web import errors
from ...dao import containerstorage
from .factory import create_provider
from .. import mappers, models


COMPUTE_DISPATCHERS = [ 'cloud-scale', 'compute-dispatcher' ]

def is_compute_dispatcher(device_type):
    """Whether or not the given device_type is a compute dispatcher"""
    return device_type in COMPUTE_DISPATCHERS


def get_provider(provider_id):
    """Get the provider document matching provider_id, or None if not found.

    Args:
        provider_id (str): The provider id

    Returns:
        The provider document (without config)

    Raises:
        APINotFoundException: If the provider does not exist.
    """
    mapper = mappers.Providers()
    result = mapper.get(provider_id)
    if not result:
        raise errors.APINotFoundException('Provider {} not found!'.format(provider_id))
    return _scrub_config(result)


def get_provider_config(provider_id, full=False):
    """Get the provider configuration matching provider_id, or None if not found.

    Args:
        provider_id (str): The provider id
        full (bool): Whether or not to include confidential fields

    Returns:
        The provider configuration

    Raises:
        APINotFoundException: If the provider does not exist.
    """
    mapper = mappers.Providers()
    result = mapper.get(provider_id)
    if not result:
        raise errors.APINotFoundException('Provider {} not found!'.format(provider_id))

    if full:
        # Cannot get storage provider config this way
        if result.provider_class != models.ProviderClass.compute:
            raise errors.APIPermissionException()
        return result.config

    # Create provider instance
    provider_inst = create_provider(result.provider_class,
        result.provider_type, result.config)

    return provider_inst.get_redacted_config()


def get_providers(provider_class=None):
    """Get all providers matching the given type, without config.

    Args:
        provider_class (ProviderClass|str): The provider class, if filtering is desired

    Yields:
        Provider: The next provider matching the given class
    """
    mapper = mappers.Providers()
    for provider in mapper.find_all(provider_class):
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
        raise errors.APINotFoundException('Provider {} not found!'.format(provider_id))

    # NOTE: We do NOT permit updating provider class or type
    if 'provider_class' in doc:
        raise errors.APIValidationException('Cannot change provider class!')

    if 'provider_type' in doc:
        raise errors.APIValidationException('Cannot change provider type!')

    if 'config' in doc:
        # Validate the new configuration
        provider_inst = create_provider(current_provider.provider_class,
            current_provider.provider_type, doc['config'])
        provider_inst.validate_config()

    mapper.patch(provider_id, doc)


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
                    raise errors.APIValidationException('Cannot change {} provider once set!'.format(provider_class))

                updates[provider_class] = True

    # Verify that the user is admin
    if (updates['storage'] or updates['compute']) and not is_admin:
        raise errors.APIPermissionException('Changing providers requires site-admin!')

    # Verify that provider exists and is the correct type
    for provider_class in ('compute', 'storage'):
        if not updates[provider_class]:
            continue
        storage_provider = get_provider(provider_ids[provider_class])
        if storage_provider.provider_class != models.ProviderClass(provider_class):
            raise errors.APIValidationException('Invalid storage provider class: {}'.format(
                storage_provider.provider_class))


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
    if isinstance(provider_class, models.ProviderClass):
        provider_key = provider_class.value
    else:
        provider_key = provider_class

    # In case we started with group or project
    result = container.get('providers', {}).get(provider_key)
    is_site = False

    if result is None:
        # Search stack (project then group)
        next_levels = ['group', 'project']
        parents = container.get('parents', {})

        while next_levels and result is None:
            parent_type = next_levels.pop()
            if parent_type not in parents:
                continue

            parent_storage = containerstorage.cs_factory(parent_type)
            parent = parent_storage.get_el(parents[parent_type])

            if not parent:
                config.log.warn('Could not find %s for container: %s',
                        parent_type, container.get('_id'))
                continue

            result = parent.get('providers', {}).get(provider_key)

    # Load site config
    if result is None:
        if site_settings is None:
            site_mapper = mappers.SiteSettings()
            site_settings = site_mapper.get()
        if site_settings:
            providers = site_settings.providers or {}
            result = providers.get(provider_key)
            is_site = bool(result)

    return is_site, result


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
    gear_name = gear.get('gear', {}).get('name')
    if gear_name is None:
        raise errors.APIValidationException('Gear {} has no name!'.format(gear.get('_id')))

    site_mapper = mappers.SiteSettings()
    site_settings = site_mapper.get() or models.SiteSettings(None, None)

    is_center_gear = gear_name in (site_settings.center_gears or [])

    if is_center_gear:
        # Check inputs to see if there are any device origins
        center_pays = False
        for inp in inputs:
            origin_type = inp.get('origin', {}).get('type')
            if origin_type == 'device':
                center_pays = True
                break

        if center_pays:
            return site_settings.get('providers', {}).get('compute')

    # Otherwise lookup effective provider id
    is_site, provider_id = get_provider_id_for_container(destination, 'compute', site_settings=site_settings)
    if is_site:
        config.log.info('Rejecting job for gear_name=%s, destination=%s because there is no valid provider',
            gear_name, destination['_id'])
        return None
    return provider_id


def _scrub_config(provider):
    """Remove config attribute from provider model

    Args:
        provider (Provider): The provider model

    Returns:
        Provider: The provider that was passed in"""
    if provider is not None:
        del provider.config
    return provider
