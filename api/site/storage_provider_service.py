""" Service layer for procesing provider business logic """
from flywheel_common.providers import ProviderClass, create_provider

# # # WHY Does this import not work when this file was under the providers dir
from . import get_site_settings
from ..types import Origin
from . import providers
from .. import config

class StorageProviderService(object):

    # pylint: disable=unused-argument
    def determine_provider(self, origin, container=None, file_size=None, force_site_provider=False):
        """
        Determines which storage provider to use based on the origin of the file

        :param Origin origin: A dict with the following definition {type: string, id: string}
        :param dict container: the container in which the file is being placed
        :param int file_size: Size of the file, will not be known for signed urls.
        :param bool force_site_provider: Override that forces site provider selection
        :rtype StorageProvider:  Returns the provider
        :raises ValueError:
        """

        site_doc = get_site_settings()
        if not site_doc.providers.get('storage'):
            raise ValueError('Site settings are not configured for a storage provider')

        if not config.is_multiproject_enabled():
            return providers.get_provider(site_doc.providers['storage'])

        if force_site_provider:
            return providers.get_provider(site_doc.providers['storage'])

        if origin['type'] == Origin.device.value:
            return providers.get_provider(site_doc.providers['storage'])


        if origin['type'] == Origin.job.value:
            from ..jobs.jobs import Job
            job = Job.get(origin['id'])

            if job.gear_info['name'] in site_doc.center_gears:
                return providers.get_provider(site_doc.providers['storage'])
            is_site_provider, provider_id = providers.get_provider_id_for_container(container, ProviderClass.storage, site_doc)

            if not is_site_provider:
                return providers.get_provider(provider_id)

            raise ValueError('No storage provider assigned for this job action')

        if origin['type'] == Origin.user.value:
            is_site_provider, provider_id = providers.get_provider_id_for_container(container, ProviderClass.storage, site_doc)
            if not is_site_provider:
                return providers.get_provider(provider_id)
            # TODO: We should only allow site if the quota is not exceeded but for now just default to site provider
            return providers.get_provider(site_doc.providers['storage'])
            #if file_size and file_size < group.storage_quota:
            #    return providers.get_provider(site_doc.providers['storage'])
            #raise ValueError('No storage provider assigned for this user action')

        raise ValueError('No storage provider assigned')

    def get_local_storage(self):
        """ Local storage is a storage plugin that supports get_fs. But it will not clean up automatically"""
        return create_provider(ProviderClass.storage.value, 'local', 'temp_storage',
                               {'path': config.local_fs_url}, None)
