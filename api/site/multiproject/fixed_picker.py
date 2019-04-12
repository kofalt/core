"""Provides a picker that always returns the site provider"""
from flywheel_common.providers import ProviderClass
from .provider_picker import ProviderPicker
from .. import mappers, models

class FixedProviderPicker(ProviderPicker):
    """Fixed picker strategy for providers"""
    def __init__(self):
        super(FixedProviderPicker, self).__init__()
        self.site_settings_mapper = mappers.SiteSettings()

    def get_provider_id_for_container(self, container, provider_class, site_settings=None):
        if isinstance(provider_class, ProviderClass):
            provider_key = provider_class.value
        else:
            provider_key = provider_class
        provider_id = self._get_provider(provider_key, site_settings=site_settings)
        # is_site is true, iff provider_id was found
        return bool(provider_id), provider_id

    def get_compute_provider_id_for_job(self, gear, destination, inputs):
        return self._get_provider('compute')

    def _get_provider(self, provider_key, site_settings=None):
        """Get the site provider for the given key"""
        if site_settings is None:
            site_settings = self.site_settings_mapper.get() or models.SiteSettings(None, None)
        providers = site_settings.providers or {}
        return providers.get(provider_key)
