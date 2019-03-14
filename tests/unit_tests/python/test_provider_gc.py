import datetime
import pytest

from api.site.providers.gc_compute_provider import GCComputeProvider

from api.web import errors

origin = { 'type': 'user', 'id': 'user@test.com' }
config = {
    'client_id': 12345,
    'client_email': 'user@google.com',
    'private_key': '------BEGIN PRIVATE KEY-----\n your key here \n------END PRIVATE KEY-----',
    'private_key_id': 12321321,
    'client_x509_cert_url': 'www.google.com/mycert',
    'project_id': 'test_project'
}

def test_instantiate(mocker):
    # The good case
    gc = GCComputeProvider(config)
    assert gc is not None
    with mocker.patch.object(GCComputeProvider, '_validate_permissions', return_value=True):
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


def test_redacted_config():
    gc = GCComputeProvider(config)
    assert gc is not None
    redacted = gc.get_redacted_config()
    assert 'client_email' in redacted
    assert 'client_id' in redacted
    assert 'project_id' in redacted
    # We should have only those explicit data points in the redacted config
    assert len(redacted) == 3



