import pytest

from api.site import providers, models
from api.web import errors

# TODO: make a key so that we can test the actual permissison validation
config = {
    'secret_access_key': 'XXXXXXXXXXXXXXXX',
    'access_key': 'XXXXXXXXXXXXXXX',
    'region': 'us-east-2',
    'bucket': 'some-test-bucket',
    'path' : 'some-path'
}

def test_instantiate(mocker):

    mocker.patch('api.site.providers.aws_storage_provider.create_flywheel_fs', return_value={'aws_test': 'test'})
    mocker.patch.object(providers.AWSStorageProvider, '_test_files', return_value=True)

    # The good case
    s3 = providers.AWSStorageProvider(config)
    assert s3 is not None
    with mocker.patch.object(providers.AWSStorageProvider, '_validate_permissions', return_value=True):
        s3.validate_config()
        s3._validate_permissions.assert_called
    assert s3.storage_plugin == {'aws_test': 'test'}
    assert s3.storage_url == "s3://" + config['bucket'] + '/' + config['path']


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

    config.pop('bucket')
    with pytest.raises(errors.APIValidationException):
        s3 = providers.AWSStorageProvider(config)
        s3.validate_config()
    config['bucket'] = 'some-test-bucket'
