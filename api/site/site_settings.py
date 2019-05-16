from flywheel_common.providers import ProviderClass
from . import models, mappers, providers
from ..jobs import gears
from ..web import errors

def get_site_settings():
    """Get the current site settings, or default settings.

    Returns:
        SiteSettings: The current site settings, or default settings
            if the settings have not yet been created.
    """
    mapper = mappers.SiteSettings()
    result = mapper.get()
    if result is None:
        return get_default_site_settings()
    return result


def update_site_settings(doc, log):
    """Update the site settings, with validation.

    Args:
        doc (dict): The update to apply

    Raises:
        APIValidationException: If invalid center gears are provided
    """
    if 'center_gears' in doc:
        # Get a list of valid gear names
        valid_names = { gear_doc['gear']['name'] for gear_doc in gears.get_gears() }

        invalid_names = set()
        for gear_name in doc['center_gears']:
            if gear_name not in valid_names:
                invalid_names.add(gear_name)

        if invalid_names:
            raise errors.APIValidationException('The following gear(s) do not exist: {}'.format(', '.join(invalid_names)))

    if 'providers' in doc:
        # Get current settings
        current_site = get_site_settings()
        providers.validate_provider_updates(current_site, doc['providers'], True)

    # Log critical path updates
    if 'center_gears' in doc:
        log.info('Updating center gears to: %s', doc['center_gears'])

    if 'providers' in doc:
        log.info('Updating site providers to: %s', doc['providers'])

    mapper = mappers.SiteSettings()
    return mapper.patch(doc)


def get_default_site_settings():
    """Return the default site settings.

    Returns:
        SiteSettings: The default site settings
    """
    providers_ = {}
    for class_ in ProviderClass:
        providers_[class_.value] = None

    return models.SiteSettings(center_gears=None, providers=providers_)
