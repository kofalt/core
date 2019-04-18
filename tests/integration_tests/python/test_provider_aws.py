import datetime
import pytest

from flywheel_common import errors
from flywheel_plugins.providers.storage.aws_storage_provider import AWSStorageProvider

from api.site import providers, models

# TODO: make a key so that we can test the actual permissison validation
config = {
    'region': 'us-east-2',
    'bucket': 'some-test-bucket',
    'path' : 'some-path'
}
creds = {
    'secret_access_key': 'XXXXXXXXXXXXXXXX',
    'access_key': 'XXXXXXXXXXXXXXX',
}
origin = {'type': 'user', 'id': 'user@user.com'} 

def test_instantiate(mocker):

    mocker.patch('flywheel_common.providers.storage.base.create_flywheel_fs', return_value={'aws_test': 'test'})
    mocker.patch.object(AWSStorageProvider, '_test_files', return_value=True)

    # The good case
    s3 = AWSStorageProvider(provider_class='storage', provider_type='aws', provider_label='Test', config=config, creds=creds)
    s3.created = s3.modified = datetime.datetime.utcnow()
    s3.origin = origin
    assert s3 is not None
    #Make this a real test with real creds
    with mocker.patch.object(AWSStorageProvider, 'validate_permissions', return_value=True):
        s3.validate()
    assert s3.storage_plugin == {'aws_test': 'test'}


    s3.creds['secret_access_key'] = None
    with pytest.raises(errors.ValidationError):
        s3.validate()
    s3.creds['secret_access_key'] = 'XXXXXXXXXXXX'

    s3.creds['access_key'] = None
    with pytest.raises(errors.ValidationError):
        s3.validate()
    s3.creds['access_key'] = 'XXXXXXXXXXXXXXXX'

    s3.config['region'] = None
    with pytest.raises(errors.ValidationError):
        s3.validate()
    s3.config['region'] = 'us-east-2'

    s3.config.pop('bucket')
    with pytest.raises(errors.ValidationError):
        s3.validate()
    s3.creds['bucket'] = 'some-test-bucket'
