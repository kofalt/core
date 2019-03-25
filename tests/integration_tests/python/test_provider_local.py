import pytest

from api.site import providers, models
from api.web import errors

config = {
    'path': 'some/valid/path'
}

def test_instantiate(mocker):

    class_= models.provider.ProviderClass.storage
    mocker.patch('api.site.providers.local_storage_provider.create_flywheel_fs', return_value={'test': 'test'})
    mocker.patch.object(providers.LocalStorageProvider, '_test_files', return_value=True)
    
    # The good case
    storage = providers.LocalStorageProvider(config)
    assert storage is not None
    with mocker.patch.object(providers.LocalStorageProvider, '_validate_permissions', return_value=True):
        storage.validate_config()
        storage._validate_permissions.assert_called
    assert storage.storage_plugin == {'test':'test'}
    assert storage.storage_url == 'osfs://' + config['path']
    
    config.pop('path')
    with pytest.raises(errors.APIValidationException):
        storage = providers.LocalStorageProvider(config)
        storage.validate_config()
    config['path'] = 'some/valid/path'
