import datetime

from mock import patch

import bson
import pytest

from flywheel_common import storage
from api.config import local_fs_url
from api.web import errors
from api.site import models, mappers, providers, multiproject
from api.site.providers.factory import ProviderKey
from api.storage.py_fs.py_fs_storage import PyFsStorage

origin = { 'type': 'user', 'id': 'user@test.com' }
provider_config = { 'key': 'value' }

def _make_provider(cls=models.ProviderClass.compute):
    return models.Provider(cls, 'sample', 'Sample Test', origin, provider_config)


class SampleProvider(providers.BaseProvider):
    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(models.ProviderClass.compute, 'sample')

    def validate_config(self):
        if 'key' not in self.config:
            raise errors.APIValidationException('Expected "key" in config!')

    def get_redacted_config(self):
        result = self.config.copy()
        result['key'] = None
        return result


# === Model Tests ===
def test_provider_delattr():
    provider = _make_provider()
    del provider.config
    assert provider.config is None
    assert 'config' not in provider.to_dict()

# === Mapper Tests ===
def test_provider_mapper_insert(api_db):
    mapper = mappers.Providers(api_db)

    provider = _make_provider()
    assert provider.provider_id is None

    provider_id = mapper.insert(provider)

    assert provider_id is not None
    try:
        # Exists and is set
        assert provider.provider_id == provider_id

        # Pull the document
        doc = api_db.providers.find_one({'_id': provider_id})
        assert doc
        assert doc['_id'] == provider_id
        assert 'created' in doc
        assert 'modified' in doc
        assert isinstance(doc['created'], datetime.datetime)
        assert isinstance(doc['modified'], datetime.datetime)
        assert doc['provider_class'] == 'compute'
        assert doc['provider_type'] == 'sample'
        assert doc['label'] == 'Sample Test'
        assert doc['origin'] == origin
        assert doc['config'] == provider_config

    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_get(api_db):
    # Insert provider
    mapper = mappers.Providers(api_db)
    provider = _make_provider()
    provider_id = mapper.insert(provider)

    try:
        # Find by arbitrary object id (None)
        result = mapper.get(bson.ObjectId())
        assert result is None

        # Find by ObjectId
        result = mapper.get(provider_id)
        assert result is not None
        assert result.provider_id == provider_id
        assert result.to_dict() == provider.to_dict()

        # Find by string
        result = mapper.get(str(provider_id))
        assert result.to_dict() == provider.to_dict()
    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_patch(api_db):
    # Insert provider
    mapper = mappers.Providers(api_db)
    provider = _make_provider()
    provider_id = mapper.insert(provider)

    try:
        config2 = { 'new_key': 'new_value' }
        mapper.patch(provider_id, {'label': 'My Provider', 'config': config2})

        # Find by ObjectId
        result = mapper.get(provider_id)

        assert result.modified >= result.created
        assert result.label == 'My Provider'
        assert result.config == config2
        assert result.provider_class == models.ProviderClass.compute
    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_find_all(api_db):
    compute_provider = _make_provider()
    storage_provider = _make_provider(cls=models.ProviderClass.storage)

    mapper = mappers.Providers(api_db)
    cid = mapper.insert(compute_provider)
    sid = mapper.insert(storage_provider)

    try:
        results = list(mapper.find_all(models.ProviderClass.storage))
        # This provider is the default site provider so exclude it from our tests if present
        for result in results:
            if result.label == 'Local Storage':
                results.remove(result)

        assert len(results) == 1
        assert results[0].to_dict() == storage_provider.to_dict()

        results = list(mapper.find_all('compute'))
        assert len(results) >= 1
        dict_results = map(lambda x: x.to_dict(), results)
        assert compute_provider.to_dict() in dict_results

        results = list(mapper.find_all('nothing'))
        # This provider is the default site provider so exclude it from our tests if present
        for result in results:
            if result.label == 'Local Storage':
                results.remove(result)

        assert len(results) == 0

        results = list(mapper.find_all())
        for result in results:
            if result.label == 'Local Storage':
                results.remove(result)
        assert len(results) == 2

    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

# === Factory Tests ===
def test_provider_factory_error():
    # Non-existent storage
    with pytest.raises(ValueError):
        provider = providers.create_provider(models.ProviderClass.storage, 'garbage', {})

def test_provider_factory_static_compute():
    # Static compute
    provider = providers.create_provider(models.ProviderClass.compute, 'static', provider_config)
    assert provider is not None
    assert provider.config == provider_config

    with pytest.raises(errors.APIValidationException):
        provider.validate_config()

    provider.config = {}
    provider.validate_config()  # Only empty config is valid for static

def test_provider_factory_storage(mocker):
    # spy_fs = mocker.spy(storage, 'create_flywheel_fs')
    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    test_config = {'path': local_fs_url}
    provider = providers.create_provider(models.ProviderClass.storage, 'osfs', test_config)
    # The call to create_flywheel_fs is different instances.
    # We can assume it was called if the storage_plugins is created. But it might have been called 2 or more times
    # TODO: find a way to mock an interface function with spy.. the count does not get recorded
    #assert storage.create_flywheel_fs.call_count == 1
    assert provider is not None
    assert provider.storage_plugin is not None

    assert isinstance(provider, providers.LocalStorageProvider)
    assert provider.config == test_config
    assert isinstance(provider.storage_plugin, PyFsStorage)


# === Repository Tests ===
def test_provider_repository_insert_and_update(api_db):
    # Invalid provider type
    provider = models.Provider(models.ProviderClass.storage, 'garbage', 'Label', origin, {})
    with pytest.raises(errors.APIValidationException):
        providers.insert_provider(provider)

    # Invalid provider config
    provider = models.Provider(models.ProviderClass.compute, 'static', 'Label', origin, provider_config)
    with pytest.raises(errors.APIValidationException):
        providers.insert_provider(provider)

    # Valid provider config
    provider = models.Provider(models.ProviderClass.compute, 'static', 'Label', origin, {})
    provider_id = providers.insert_provider(provider)
    assert provider_id is not None

    try:
        # Load from data store
        mapper = mappers.Providers()
        result = mapper.get(provider_id)
        assert result.to_dict() == provider.to_dict()

        # Try to update non-existent
        with pytest.raises(errors.APINotFoundException):
            providers.update_provider(bson.ObjectId(), {'label': 'New Label'})

        # Try to update provider class
        with pytest.raises(errors.APIValidationException):
            providers.update_provider(str(provider_id), {'provider_class': 'storage'})

        # Try to update provider type
        with pytest.raises(errors.APIValidationException):
            providers.update_provider(str(provider_id), {'provider_type': 'garbage'})

        # Try to set invalid config
        with pytest.raises(errors.APIValidationException):
            providers.update_provider(provider_id, {'config': {'x':'y'}})

        # Successful update
        providers.update_provider(provider_id, {'label': 'New Label', 'config': {}})

        result = mapper.get(provider_id)
        assert result.config == {}
        assert result.label == 'New Label'
    finally:
        api_db.providers.remove({'_id': provider_id})

def test_provider_repository_load(api_db):
    compute_provider = _make_provider()
    storage_provider = _make_provider(cls=models.ProviderClass.storage)

    mapper = mappers.Providers()
    cid = mapper.insert(compute_provider)
    sid = mapper.insert(storage_provider)

    try:
        # Not found
        with pytest.raises(errors.APINotFoundException):
            providers.get_provider(bson.ObjectId())

        with pytest.raises(errors.APINotFoundException):
            providers.get_provider_config(bson.ObjectId())

        # Load with get_provider
        result = providers.get_provider(str(cid))
        expected = compute_provider.to_dict()
        del expected['config']
        assert result.to_dict() == expected

        # Load all
        results = list(providers.get_providers())
        # This provider is the default site provider so exclude it from our tests if present
        for result in results:
            if result.label == 'Local Storage':
                results.remove(result)

        assert len(results) == 2

        # Load by type
        results = list(providers.get_providers('compute'))
        assert len(results) >= 1
        dict_results = map(lambda x: x.to_dict(), results)
        assert expected in dict_results

        # Load redacted config
        result = providers.get_provider_config(cid)
        assert result == {'key': None}

        # Load full provider config
        result = providers.get_provider_config(cid, full=True)
        assert result == compute_provider.config
    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

def test_validate_provider_updates(api_db):
    compute_provider = _make_provider()
    storage_provider = _make_provider(cls=models.ProviderClass.storage)

    mapper = mappers.Providers()
    cid = mapper.insert(compute_provider)
    sid = mapper.insert(storage_provider)

    try:
        # Starting from empty container
        container = {}

        # No providers
        updates = None
        providers.validate_provider_updates(container, updates, False)
        providers.validate_provider_updates(container, updates, True)

        # Empty providers
        updates = {}
        providers.validate_provider_updates(container, updates, False)
        providers.validate_provider_updates(container, updates, True)

        # Validate compute provider id
        updates = {'compute': bson.ObjectId()}
        with pytest.raises(errors.APINotFoundException):
            providers.validate_provider_updates(container, updates, True)

        # Validate storage provider id
        updates = {'storage': bson.ObjectId()}
        with pytest.raises(errors.APINotFoundException):
            providers.validate_provider_updates(container, updates, True)

        # String id for compute provider
        updates = {'compute': str(cid)}
        providers.validate_provider_updates(container, updates, True)
        assert isinstance(updates['compute'], bson.ObjectId)

        # Changing without admin is a permission error
        with pytest.raises(errors.APIPermissionException):
            providers.validate_provider_updates(container, updates, False)

        # No-change is OK
        container = {'providers': {'compute': cid}}
        providers.validate_provider_updates(container, updates, False)

        # String id for compute provider
        container = {}
        updates = {'storage': str(sid)}
        providers.validate_provider_updates(container, updates, True)
        assert isinstance(updates['storage'], bson.ObjectId)

        # Changing without admin is a permission error
        with pytest.raises(errors.APIPermissionException):
            providers.validate_provider_updates(container, updates, False)

        # No-change is OK
        container = {'providers': {'storage': sid}}
        providers.validate_provider_updates(container, updates, False)

        # Cannot change after set
        container = {'providers': {'storage': bson.ObjectId()}}
        with pytest.raises(errors.APIValidationException):
            providers.validate_provider_updates(container, updates, True)

        updates = {'compute': str(cid)}
        container = {'providers': {'compute': bson.ObjectId()}}
        with pytest.raises(errors.APIValidationException):
            providers.validate_provider_updates(container, updates, True)

        # Invalid provider type tests
        updates = {'storage': cid}
        container = {}
        with pytest.raises(errors.APIValidationException):
            providers.validate_provider_updates(container, updates, True)

        updates = {'compute': sid}
        container = {}
        with pytest.raises(errors.APIValidationException):
            providers.validate_provider_updates(container, updates, True)
    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

def test_get_provider_picker():
    from api.site.multiproject.fixed_picker import FixedProviderPicker
    from api.site.multiproject.multiproject_picker import MultiprojectProviderPicker

    picker = providers.repository._get_provider_picker()
    assert isinstance(picker, MultiprojectProviderPicker)

    with patch('api.site.providers.repository.config') as patched_config:
        patched_config.is_multiproject_enabled.return_value = True

        picker = providers.repository._get_provider_picker()
        assert isinstance(picker, MultiprojectProviderPicker)

        patched_config.is_multiproject_enabled.return_value = False

        picker = providers.repository._get_provider_picker()
        assert patched_config.is_multiproject_enabled.called
        assert isinstance(picker, FixedProviderPicker)

def test_storage_provider_service():
    # TODO: put the business logic in here with regard to selecting storage provider
    pass

