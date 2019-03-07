import datetime

import bson
import pytest

from api.web import errors
from api.site.models import Provider, ProviderClass
from api.site.mappers import ProviderMapper
from api.site import providers
from api.site.providers AWSStorageProvider

# TODO: make a key so that we can test the actual permissison validation
config = {
    'secret_access_key': 'XXXXXXXXXXXXXXXX',
    'access_key': 'XXXXXXXXXXXXXXX',
    'region': 'us-east-2',
    'bucket': 'roy-storage-dev'
}

def test_instantiate(mocker):
    class_= ProviderClass.storage

    # The good case
    s3 = AWSStorageProvider(config)
    assert s3 is not None
    with mocker.patch.object(AWSStorageProvider, '_validate_permissions', return_value=True ):
        s3.validate_config()
        s3._validate_permissions.assert_called
    

    config['secret_access_key'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = AWSStorageProvider(config)
        s3.validate_config()
    config['secret_access_key'] = 'XXXXXXXXXXXX'
    
    config['access_key'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = AWSStorageProvider(config)
        s3.validate_config()
    config['access_key'] = 'XXXXXXXXXXXXXXXX'
    
    config['region'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = AWSStorageProvider(config)
        s3.validate_config()
    config['region'] = 'us-east-2'

    config['bucket'] = None
    with pytest.raises(errors.APIValidationException):
        s3 = AWSStorageProvider(config)
        s3.validate_config()
    config['bucket'] = 'roy-stroage-dev'
    
