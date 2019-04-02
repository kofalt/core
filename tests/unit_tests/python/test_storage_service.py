'''Test the provider selection from the storage service'''
import pytest

from api.site.storage_provider_service import StorageProviderService

def test_provider_selection(mocker, with_site_settings):

    container = {
        'label': 'Test Container',
        'providers': {
            'storage': 'from_test_container'
        }
    }
    file_size = 1000

    # return is an object with the document as a dictionary so we need to stub the same
    mocker.patch('api.site.storage_provider_service.get_site_settings', return_value=site_settings)
    mocker.patch('api.site.providers.get_provider_instance', new=mocked_return)
    mocker.patch('api.jobs.jobs.Job.get', return_value=job)
    storage_service = StorageProviderService()

    # Error if origin is not matched
    provider = None
    with pytest.raises(ValueError):
        provider = storage_service.determine_provider({'type': 'bad'}, None, None)
    assert provider == None

    # device origin gets the site provider
    provider = storage_service.determine_provider({'type': 'device'}, None, file_size)
    assert provider == site_settings.providers['storage']


    # Job origin gets site when using center gears
    provider = storage_service.determine_provider({'type': 'job', 'id': '1234'}, container, file_size)
    assert provider == site_settings.providers['storage']

    # Job origin without a center gear and the selection moves up to the site provider.
    mocker.patch('api.site.providers.get_provider_id_for_container', return_value=(True, 1234))
    mocker.patch('api.jobs.jobs.Job.get', return_value=job_no_gear)
    provider = None
    with pytest.raises(ValueError):
        provider = storage_service.determine_provider({'type': 'job', 'id': '1234'}, container, file_size)
    assert provider == None

    # Job origin without a center gear but a parent project/group has a provider
    mocker.patch('api.site.providers.get_provider_id_for_container', return_value=(False, 4321))
    provider = storage_service.determine_provider({'type': 'job', 'id': '1234'}, container, file_size)
    assert provider == 4321


    # user origin gets the container provider or a parent group/project provider
    provider = storage_service.determine_provider({'type': 'user'}, container, file_size)
    assert provider == 4321

    mocker.patch('api.site.providers.get_provider_id_for_container', return_value=(True, 2222))
    # This will be true once the storage quota checks are implemented
    # with pytest.raises(ValueError):
        # provider = storage_service.determine_provider({'type': 'user'}, container, file_size)
    # Without quota checks we just return the site provider for now
    provider = storage_service.determine_provider({'type': 'user'}, container, file_size)
    assert provider == site_settings.providers['storage']

def mocked_return(value):
    return value

# These are mock objects since we need objects with attributes not dictionaries
class job: 
    gear_info = {'name': 'good_gear'}

class job_no_gear: 
    gear_info = {'name': 'not_a_gear'}

class site_settings:
        providers = {'storage': 'from_site_settings'}
        center_gears = ['good_gear']

