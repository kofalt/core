""" Service layer for procesing provider business logic """

# # # WHY Does this import not work when this file was under the providers dir
from . import get_site_settings
from ..types import Origin
from ..dao.hierarchy import get_container
from . import providers
from .models.provider import ProviderClass
from ..config import local_fs_url

class StorageProviderService(object):

    def determine_provider(self, origin, container=None, job=None, file_size=None):
        """
        Determines which storage provider to use based on the origin of the file
        If None is used then no storage provider is configured and you can not read/write files

        :param Origin origin: A dict with the following definition {type: string, id: string}
        :param dict job: A dict with the following definition
        :param dict container: the container in which the file is being placed
        :param int file_size: Size of the file, will not be known for signed urls.
        :rtype StorageProvider | None:  Returns the provider or none if nothing is set on site level

        TODO: If we get a none should that be an error case?  When do we want no storage to be allowed?
        """


        # For now just always return the site provider if its set
        site_doc = get_site_settings()
        if site_doc.get('providers') and site_doc.providers.get('storage'):
            provider = providers.get_provider_instance(site_doc.providers['storage'])
            if not provider:
                raise ValueError('Storage provider can not be found for this site')
            return provider
        else:
            raise ValueError('Site settings are not configured for a storage provider')
            #return None


        site_doc = get_site_settings()
        if origin['type'] == Origin.device.value:
            if not site_doc.providers['storage']:
                return None

            # Repo should return the hydrated object
            #return get_provider(site.storage_provider)
            return providers.get_provider_instance(site_doc.providers['storage'])

        if job and origin['type'] == Origin.job.value:
            # Im not sure if the doc contains the gear name or the id. It seems to be id??
            if job.gear_info['name'] in site_doc.center_gears:
                return providers.get_provider_instance(site_doc.providers['storage'])

        if origin['type'] == Origin.user.value:
            # Projects will have this key other container types will not
            provider_id = container.providers.storage if container.get('providers', None) else None
            if not provider_id:
                group = get_container('groups', container.group)
                provider_id = group.provider.storage

            if not provider_id:
                pass
                #if file_size and file_size < group.storage_quota
                    ## TODO :cehck if the group quote is full use the site.
                    #provider_id = site.storage_provider

            if not provider_id:
                return None

            return providers.get_provider_instance(site_doc.providers['storage'])

    def get_local_storage(self):
        """ Local storage is a storage plugin that supports get_fs. But it will not clean up automatically"""
        site_doc = get_site_settings()
        return providers.factory.create_provider(ProviderClass.storage, 'osfs', {
            'path': local_fs_url
            })
