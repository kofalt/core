import datetime

from mock import patch

import bson
import pytest

from flywheel_common import storage
from flywheel_common import errors
from flywheel_common.providers import ProviderClass, create_provider
from flywheel_common.providers.provider import BaseProvider, BaseProviderSchema
from api.site.providers.local_storage_provider import LocalStorageProvider, LocalStorageProviderSchema
from api.site.providers.static_compute_provider import StaticComputeProvider, StaticComputeProviderSchema

from api.config import local_fs_url
from api.site import mappers, multiproject
from api.site import providers
from api.storage.py_fs.py_fs_storage import PyFsStorage

origin = { 'type': 'user', 'id': 'user@test.com' }
provider_config = { 'key': 'value' }

def _make_provider(cls=ProviderClass.storage.value):
    provider = BaseProvider(
        provider_class=cls,
        provider_type='test',
        provider_label='test provider',
        config={'test': 'value'},
        creds={'test': 'value2'})

    provider.origin = {'type': 'user', 'id': 'user@test.com'}
    provider.created = datetime.datetime.utcnow()
    provider.modified = provider.created
    provider._schema = BaseProviderSchema()
    return provider

def _make_compute_provider():
    provider = StaticComputeProvider(
        provider_class='compute',
        provider_type='static',
        provider_label='test compute provider',
        config={},
        creds=None)

    provider.origin = {'type': 'user', 'id': 'user@test.com'}
    provider.created = datetime.datetime.utcnow()
    provider.modified = provider.created
    provider._schema = StaticComputeProviderSchema()
    return provider

def _make_storage_provider():
    provider = LocalStorageProvider(
        provider_class='storage',
        provider_type='local',
        provider_label='test storage provider',
        config={'path': '/var'},
        creds=None)

    provider.origin = {'type': 'user', 'id': 'user@test.com'}
    provider.created = datetime.datetime.utcnow()
    provider.modified = provider.created
    provider._schema = LocalStorageProviderSchema()
    return provider

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
        assert doc['provider_class'] == provider.provider_class
        assert doc['provider_type'] == provider.provider_type
        assert doc['label'] == provider.label
        assert doc['origin'] == origin
        #assert doc['config'] == provider_config

    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_storage_provider_mapper_get(api_db):
    # Insert provider
    mapper = mappers.Providers(api_db)
    provider = _make_storage_provider()
    provider_id = mapper.insert(provider)

    try:
        # Find by arbitrary object id (None)
        result = mapper.get(bson.ObjectId())
        assert result is None

        # Find by ObjectId
        result = mapper.get(provider_id)
        assert result is not None
        assert result.provider_id == provider_id
        assert provider._schema.dump(result) == provider._schema.dump(provider)

        # Find by string
        result = mapper.get(str(provider_id))
        assert provider._schema.dump(result) == provider._schema.dump(provider)
    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_storage_provider_mapper_patch(api_db):
    # Insert provider
    mapper = mappers.Providers(api_db)
    provider = _make_storage_provider()
    provider_id = mapper.insert(provider)

    try:
        config2 = {'path': '/var/scitran'}
        provider.label = 'My Provider'
        provider.config = config2
        mapper.patch(provider_id, provider)

        # Find by ObjectId
        result = mapper.get(provider_id)

        assert result.modified >= result.created
        assert result.label == 'My Provider'
        assert result.config == config2
        assert result.provider_class == ProviderClass.storage.value
    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_find_all(api_db):
    # The base provider does not have the needed items to be persisted sucessfully
    compute_provider = _make_compute_provider()
    storage_provider = _make_storage_provider()

    mapper = mappers.Providers(api_db)
    cid = mapper.insert(compute_provider)
    sid = mapper.insert(storage_provider)

    try:
        results = list(mapper.find_all(ProviderClass.storage))
        # This provider is the default site provider so exclude it from our tests if present
        final_results = []
        for result in results:
            if result.label != 'Primary Storage':
                final_results.append(result)

        assert len(final_results) == 1
        assert final_results[0]._schema.dump(final_results[0]) == storage_provider._schema.dump(storage_provider)

        results = list(mapper.find_all(ProviderClass.compute.value))
        assert len(results) >= 1
        expected_results = compute_provider._schema.dump(compute_provider).data
        final_results = []
        for result in results:
            final_results.append(result._schema.dump(result).data)
        assert expected_results in final_results

        results = list(mapper.find_all('nothing'))
        assert len(results) == 0

        results = list(mapper.find_all())
        final_results = []
        for result in results:
            if not (result.label == 'Primary Storage' or result.label == 'Static Compute'):
                final_results.append(result)
        assert len(final_results) == 2

    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

# === Factory Tests ===
def test_provider_factory_error():
    # Non-existent storage
    with pytest.raises(errors.ValidationError):
        provider = create_provider(ProviderClass.storage.value, 'garbage', 'garbage test', {}, {})

def test_provider_factory_static_compute():
    # Static compute
    test_config = {'value': 'test'}
    provider = create_provider(ProviderClass.compute.value, 'static', 'compute test', test_config, None)
    assert provider is not None
    assert provider.config == test_config

    with pytest.raises(errors.ValidationError):
        provider.validate()
    provider.config = {}
    provider.validate()  # Only empty config is valid for static

def test_provider_factory_storage(mocker):
    # spy_fs = mocker.spy(storage, 'create_flywheel_fs')
    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    test_config = {'path': local_fs_url}
    provider = create_provider(ProviderClass.storage.value, 'local', 'local test', test_config, None)
    # The call to create_flywheel_fs is different instances.
    # We can assume it was called if the storage_plugins is created. But it might have been called 2 or more times
    # TODO: find a way to mock an interface function with spy.. the count does not get recorded
    #assert storage.create_flywheel_fs.call_count == 1
    assert provider is not None
    assert provider.storage_plugin is not None

    assert isinstance(provider, LocalStorageProvider)
    assert provider.config == test_config
    assert isinstance(provider.storage_plugin, PyFsStorage)


# === Repository Tests ===
def test_provider_repository_insert_and_update(api_db):
    # Invalid provider type
    provider = _make_provider(ProviderClass.storage.value)
    provider.provider_class = 'garbage'
    with pytest.raises(Exception):
        providers.insert_provider(provider)

    # Invalid provider config... needs more than just the baes implementation
    provider = _make_storage_provider()
    provider.config = {}
    with pytest.raises(errors.ValidationError):
        providers.insert_provider(provider)

    # Valid provider config
    provider = _make_storage_provider()
    provider_id = providers.insert_provider(provider)
    assert provider_id is not None

    try:
        # Load from data store
        mapper = mappers.Providers()
        result = mapper.get(provider_id)
        assert result._schema.dump(result) == provider._schema.dump(provider)

        # Try to update non-existent
        with pytest.raises(errors.ResourceNotFound):
            providers.update_provider(bson.ObjectId(), {'label': 'New Label'})

        # Try to update provider class
        with pytest.raises(errors.ValidationError):
            providers.update_provider(str(provider_id), {'provider_class': 'compute'})

        # Try to update provider type
        with pytest.raises(errors.ValidationError):
            providers.update_provider(str(provider_id), {'provider_type': 'garbage'})

        # Try to set invalid config
        with pytest.raises(errors.ValidationError):
            providers.update_provider(provider_id, {'config': {'x':'y'}})

        # Successful update
        providers.update_provider(provider_id, {'label': 'New Label', 'config': {'path': '/var'}})

        result = mapper.get(provider_id)
        assert result.config == {'path': u'/var'}
        assert result.label == 'New Label'
    finally:
        api_db.providers.remove({'_id': provider_id})

def test_provider_repository_load(api_db):
    compute_provider = _make_compute_provider()
    storage_provider = _make_storage_provider()

    mapper = mappers.Providers()
    cid = mapper.insert(compute_provider)
    sid = mapper.insert(storage_provider)

    try:
        # Not found
        with pytest.raises(errors.ResourceNotFound):
            providers.get_provider(bson.ObjectId())

        with pytest.raises(errors.ResourceNotFound):
            providers.get_provider_config(bson.ObjectId())

        # Load with get_provider
        result = providers.get_provider(str(sid))
        expected = storage_provider._schema.dump(storage_provider).data
        #del expected['config']
        assert result._schema.dump(result).data == expected

        # Load all
        results = list(providers.get_providers())
        # These are the defaults  so exclude from our tests if present
        final_results = [];
        for result in results:
            if not (result.label == 'Primary Storage' or result.label == 'Static Compute'):
                final_results.append(result)
        # Adjust once the compute providers are ready
        assert len(final_results) == 2

        # Load by type
        results = list(providers.get_providers('storage'))
        assert len(results) >= 1
        final_results = []
        for result in results:
            final_results.append(result._schema.dump(result).data)
        assert expected in final_results

        # Load redacted config
        result = providers.get_provider_config(sid)
        assert result == {'id': storage_provider.provider_id, 'path': '/var'}

        # Load full provider config
        result = providers.get_provider_config(cid, full=True)
        assert result == {'config': compute_provider.config, 'creds': {}} # Creds are empty but still returned in full config
    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

def test_validate_provider_updates(api_db):
    compute_provider = _make_compute_provider()
    compute_provider2 = _make_compute_provider()
    storage_provider = _make_storage_provider()
    storage_provider2 = _make_storage_provider()

    mapper = mappers.Providers()
    cid = mapper.insert(compute_provider)
    cid2 = mapper.insert(compute_provider2)
    sid = mapper.insert(storage_provider)
    sid2 = mapper.insert(storage_provider2)

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
        with pytest.raises(errors.ResourceNotFound):
            providers.validate_provider_updates(container, updates, True)

        # Validate storage provider id
        updates = {'storage': bson.ObjectId()}
        with pytest.raises(errors.ResourceNotFound):
            providers.validate_provider_updates(container, updates, True)

        # String id for compute provider
        updates = {'compute': str(cid)}
        providers.validate_provider_updates(container, updates, True)
        assert isinstance(updates['compute'], bson.ObjectId)

        # Setting providers for the first time is not allowed for users
        with pytest.raises(errors.PermissionError):
            providers.validate_provider_updates(container, updates, False)

        # Setting providers for the first time is allowed for admins
        providers.validate_provider_updates(container, updates, True)

        # Changing providers is not allowed for users
        container = {'providers': {'compute': cid2}}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, False)

        # Changing providers is not allowed
        container = {'providers': {'compute': cid2}}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, True)

        # No-change is OK
        container = {'providers': {'compute': cid}}
        providers.validate_provider_updates(container, updates, False)

        # String id for storage provider
        container = {}
        updates = {'storage': str(sid)}
        providers.validate_provider_updates(container, updates, True)
        assert isinstance(updates['storage'], bson.ObjectId)

        # Setting providers for the first time is not allowed for users
        with pytest.raises(errors.PermissionError):
            providers.validate_provider_updates(container, updates, False)


        # No-change is OK
        container = {'providers': {'storage': sid}}
        providers.validate_provider_updates(container, updates, False)

        # Cannot change after set as admin
        container = {'providers': {'storage': bson.ObjectId()}}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, True)

        # Cannot change after set as user
        container = {'providers': {'storage': bson.ObjectId()}}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, False)

        updates = {'compute': str(cid)}
        container = {'providers': {'compute': bson.ObjectId()}}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, True)

        # Invalid provider type tests
        updates = {'storage': cid}
        container = {}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, True)

        updates = {'compute': sid}
        container = {}
        with pytest.raises(errors.ValidationError):
            providers.validate_provider_updates(container, updates, True)
    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

def test_get_provider_picker():
    from api.site.multiproject.fixed_picker import FixedProviderPicker
    from api.site.multiproject.multiproject_picker import MultiprojectProviderPicker

    # We assume multiproject is off by default now
    picker = providers.repository._get_provider_picker()
    assert isinstance(picker, FixedProviderPicker)

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

