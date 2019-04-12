"""Provides a picker that returns the provider based on multiproject policy"""
from flywheel_common import ProviderClass
from .provider_picker import ProviderPicker
from .. import mappers, models

from ... import config
from ...web import errors
from ...dao import containerstorage

class MultiprojectProviderPicker(ProviderPicker):
    """Multiproject picker strategy for providers"""
    def __init__(self):
        super(MultiprojectProviderPicker, self).__init__()
        self.site_settings_mapper = mappers.SiteSettings()

    def get_provider_id_for_container(self, container, provider_class, site_settings=None):
        if isinstance(provider_class, ProviderClass):
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
                site_settings = self.site_settings_mapper.get()
            if site_settings:
                providers = site_settings.providers or {}
                result = providers.get(provider_key)
                is_site = bool(result)

        return is_site, result

    def get_compute_provider_id_for_job(self, gear, destination, inputs):
        gear_name = gear.get('gear', {}).get('name')
        if gear_name is None:
            raise errors.APIValidationException('Gear {} has no name!'.format(gear.get('_id')))

        site_settings = self.site_settings_mapper.get() or models.SiteSettings(None, None)

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
        is_site, provider_id = self.get_provider_id_for_container(destination, 'compute', site_settings=site_settings)
        if is_site:
            config.log.info('Rejecting job for gear_name=%s, destination=%s because there is no valid provider',
                gear_name, destination['_id'])
            return None
        return provider_id
