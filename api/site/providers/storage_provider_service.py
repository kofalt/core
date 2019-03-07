""" Service layer for procesing provider business logic """
from ..mappers.site_settings_mapper import SiteSettingsMapper
from ..mappers.provider_mapper import ProviderMapper
# from .storage_provider import StorageProvider
# from .repository import get_provider
from ...types import Origin
from ...dao.hierarchy import get_container


class StorageProviderService(object):

    def determine_provider(self, origin, container, job=None, file_size=None):
        """
        Determines which storage provider to use based on the origin of the file
        If None is used then no storage provider is configured and you can not read/write files

        :param dict origin: A dict with the following definition {type: string, id: string}
        :param dict job: A dict with the following definition
        :param dict container: the container in which the file is being placed
        :param int file_size: Size of the file, will not be known for signed urls.
        :rtype StorageProvider | None:  Returns the provider or none if nothing is set on site level
        """

        # Could the mappers just be singletons?
        site_settings_mapper = SiteSettingsMapper()
        provider_mapper = ProviderMapper()

        site_doc = site_settings_mapper.find()
        if origin == 'device':
            if not site_doc.storage_provider:
                return None

            # Repo should return the hydrated object
            #return get_provider(site.storage_provider)

            return provider_mapper.find(site_doc.storage_provider)

        if job and origin['type'] == Origin.job.value:
            if job.gear_info['name'] in site_doc.center_gears:
                return provider_mapper.find(site_doc.storage_provider)

        if origin['type'] == Origin.user.value:
            # Projects will have this key other container types will not
            provider_id = container.get('storage_provider_id', None)
            if not provider_id:
                group = get_container('groups', container.group)
                provider_id = group.storage_provider

            if not provider_id:
                pass
                #if file_size and file_size < group.storage_quota
                    ## TODO :cehck if the group quote is full use the site.
                    #provider_id = site.storage_provider

            if not provider_id:
                return None

            return provider_mapper.find(site_doc.storage_provider)
