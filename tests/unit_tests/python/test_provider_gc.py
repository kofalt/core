import datetime

import bson
import pytest

from api.web import errors
from api.site.models import Provider, ProviderClass
from api.site.mappers import ProviderMapper
from api.site import providers
from api.site.providers import GCComputeProvider

origin = { 'type': 'user', 'id': 'user@test.com' }
config = {
    'client_id': 12345,
    'client_email': 'user@google.com',
    'private_key': '------BEGIN PROVATE KEY-----\n your key here \n------END PRIVATE KEY-----',
    'private_key_id': 12321321,
    'client_x509_cert_url': 'www.google.com/mycert',
    'project_id': 'test_project'
}

def test_instantiate(mocker):
    class_= ProviderClass.compute

    # The good case
    gc = GCComputeProvider(config)
    assert gc is not None
    with mocker.patch.object(GCComputeProvider, '_validate_permissions', return_value=True ):
        gc.validate_config()
        gc._validate_permissions.assert_called
    

    config['client_id'] = None
    with pytest.raises(errors.APIValidationException):
        gc = GCComputeProvider(config)
        gc.validate_config()
    config['client_id'] = 12345
    
    config['client_email'] = None
    with pytest.raises(errors.APIValidationException):
        gc = GCComputeProvider(config)
        gc.validate_config()
    config['client_email'] = 'user@google.com'
    
    config['private_key_id'] = None
    with pytest.raises(errors.APIValidationException):
        gc = GCComputeProvider(config)
        gc.validate_config()
    config['private_key_id'] = '12321321'

    config['client_x509_cert_url'] = None
    with pytest.raises(errors.APIValidationException):
        gc = GCComputeProvider(config)
        gc.validate_config()
    config['client_x509_cert_url'] = 'www.google.com/mycert'
    
    config['project_id'] = None
    with pytest.raises(errors.APIValidationException):
        gc = GCComputeProvider(config)
        gc.validate_config()
    config['project_id'] = 'test_project'
