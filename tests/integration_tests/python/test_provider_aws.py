import pytest

from api.site import providers, models

from api.web import errors

# TODO: make a key so that we can test the actual permissison validation
config = {
    'secret_access_key': 'XXXXXXXXXXXXXXXX',
    'access_key': 'XXXXXXXXXXXXXXX',
    'region': 'us-east-2',
    'bucket': 'some-test-bucket'
}

def test_instantiate(mocker):
    class_= models.provider.ProviderClass.storage

    # The good case
    s3 = providers.AWSStorageProvider(config)
    assert s3 is not None
    with mocker.patch.object(providers.AWSStorageProvider, '_validate_permissions', return_value=True):
        s3.validate_config()
        s3._validate_permissions.assert_called
    

    config['secret_access_key'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = providers.AWSStorageProvider(config)
        s3.validate_config()
    config['secret_access_key'] = 'XXXXXXXXXXXX'
    
    config['access_key'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = providers.AWSStorageProvider(config)
        s3.validate_config()
    config['access_key'] = 'XXXXXXXXXXXXXXXX'
    
    config['region'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = providers.AWSStorageProvider(config)
        s3.validate_config()
    config['region'] = 'us-east-2'

    config['bucket'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = providers.AWSStorageProvider(config)
        s3.validate_config()
    config['bucket'] = 'some-test-bucket'
    
