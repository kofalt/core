import pytest
import datetime

from flywheel_common.errors import ValidationError
from flywheel_common.providers import ProviderClass
from api.site.providers.local_storage_provider import LocalStorageProvider

config = {
    'path': 'some/valid/path'
}
origin = { 'type': 'user', 'id': 'user@test.com' }

def test_instantiate(mocker):

    class_ = ProviderClass.storage.value
    mocker.patch('flywheel_common.providers.storage.base.create_flywheel_fs', return_value={'test': 'test'})
    mocker.patch.object(LocalStorageProvider, '_test_files', return_value=True)

    # The good case
    storage = LocalStorageProvider(
        provider_class=class_,
        provider_type='local',
        provider_label='test',
        config=config,
        creds=None)
    storage.origin = origin
    storage.modified = storage.created = datetime.datetime.utcnow()
    assert storage is not None

    storage.validate()
    assert storage.storage_plugin is not None
    assert storage.storage_plugin == {'test':'test'}

    storage.config.pop('path')
    with pytest.raises(ValidationError):
        storage.validate()
    storage.config['path'] = None
    with pytest.raises(ValidationError):
        storage.validate()
    storage.config['path'] = '/some/valid/path'

def test_redacted_config(mocker):
    class_ = ProviderClass.storage.value
    mocker.patch('flywheel_common.providers.storage.base.create_flywheel_fs', return_value={'test': 'test'})
    mocker.patch.object(LocalStorageProvider, '_test_files', return_value=True)

    storage = LocalStorageProvider(
        provider_class=class_,
        provider_type='local',
        provider_label='test',
        config=config,
        creds=None)
    storage.origin = origin
    assert storage is not None

    redacted = storage.get_redacted_config()
    assert 'id' in redacted
    assert 'path' in redacted
    # We should have only those explicit data points in the redacted config
    assert len(redacted) == 2



