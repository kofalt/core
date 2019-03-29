""" Service layer for procesing provider business logic """

# # # WHY Does this import not work when this file was under the providers dir
from . import get_site_settings
from ..types import Origin
from ..dao.hierarchy import get_container
from . import providers
from .models.provider import ProviderClass
from ..config import local_fs_url
from .providers import get_provider_id_for_container

class StorageProviderService(object):

    # pylint: disable=unused-argument
    def determine_provider(self, origin, container=None, file_size=None):
        """
        Determines which storage provider to use based on the origin of the file

        :param Origin origin: A dict with the following definition {type: string, id: string}
        :param dict job: A dict with the following definition
        :param dict container: the container in which the file is being placed
        :param int file_size: Size of the file, will not be known for signed urls.
        :rtype StorageProvider:  Returns the provider
        :raises ValueError:

        """
        site_doc = get_site_settings()
        if origin['type'] == Origin.device.value:
            return providers.get_provider_instance(site_doc.providers['storage'])


        if origin['type'] == Origin.job.value:
            from ..jobs.jobs import Job
            job = Job.get(origin['id'])

            if job.gear_info['name'] in site_doc.center_gears:
                return providers.get_provider_instance(site_doc.providers['storage'])
            provider_choice = providers.get_provider_id_for_container(container, ProviderClass.storage, site_doc)
            # Return is a tuple indicating if a site provider was returned. We dont allow bubbling up to site.
            if not provider_choice[0]:
                return providers.get_provider_instance(provider_choice[1])

            raise ValueError('No storage provider assigned for this job action')

        if origin['type'] == Origin.user.value:
            provider_choice = providers.get_provider_id_for_container(container, ProviderClass.storage, site_doc)
            if not provider_choice[0]:
                return providers.get_provider_instance(provider_choice[1])

            # TODO: We should only allow site if the quota is not exceeded but for now just default to site provider
            return providers.get_provider_instance(site_doc.providers['storage'])
            #if file_size and file_size < group.storage_quota:
            #    return providers.get_provider_instance(site_doc.providers['storage'])
            #raise ValueError('No storage provider assigned for this user action')

        raise ValueError('No storage provider assigned')

    def get_local_storage(self):
        """ Local storage is a storage plugin that supports get_fs. But it will not clean up automatically"""
        return providers.factory.create_provider(ProviderClass.storage, 'osfs', {
            'path': local_fs_url
        })
