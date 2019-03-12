import datetime

from mock import patch, Mock

import bson
import pytest

from api.web import errors
from api.site import models, mappers, providers
from api.site.providers.factory import ProviderKey

origin = { 'type': 'user', 'id': 'user@test.com' }
config = { 'key': 'value' }

def _make_provider(cls=models.ProviderClass.compute):
    return models.Provider(cls, 'sample', 'Sample Test', origin, config)


class SampleProvider(providers.BaseProvider):
    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(models.ProviderClass.compute, 'sample')

    def validate_config(self):
        if 'key' not in self.config:
            raise errors.APIValidationException('Expected "key" in config!')

    def get_redacted_config(self):
        result = config.copy()
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
        assert doc['config'] == config

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
        assert len(results) == 1
        assert results[0].to_dict() == storage_provider.to_dict()

        results = list(mapper.find_all('compute'))
        assert len(results) == 1
        assert results[0].to_dict() == compute_provider.to_dict()

        results = list(mapper.find_all('nothing'))
        assert len(results) == 0

        results = list(mapper.find_all())
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
    config = {'key': 'value'}

    # Static compute
    provider = providers.create_provider(models.ProviderClass.compute, 'static', config)
    assert provider is not None
    assert provider.config == config

    with pytest.raises(errors.APIValidationException):
        provider.validate_config()

    provider.config = {}
    provider.validate_config()  # Only empty config is valid for static

# === Repository Tests ===
def test_provider_repository_insert_and_update(api_db):
    # Invalid provider type
    provider = models.Provider(models.ProviderClass.storage, 'garbage', 'Label', origin, config)
    with pytest.raises(errors.APIValidationException):
        providers.insert_provider(provider)

    # Invalid provider config
    provider = models.Provider(models.ProviderClass.compute, 'static', 'Label', origin, config)
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
        assert len(results) == 2

        # Load by type
        results = list(providers.get_providers('compute'))
        assert len(results) == 1
        assert results[0].to_dict() == expected

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


@patch('api.site.providers.repository.mappers.SiteSettings')
@patch('api.site.providers.repository.containerstorage.cs_factory')
def test_get_provider_id_for_container(mock_cs_factory, MockSiteSettingsCls):
    cls = models.ProviderClass.compute

    site_provider_id = bson.ObjectId()
    group_provider_id = bson.ObjectId()
    project_provider_id = bson.ObjectId()

    container = {
        '_id': 'test',
        'parents': {
            'group': bson.ObjectId(),
            'project': bson.ObjectId()
        }
    }

    # Mock site settings & container storage
    MockSiteSettings = Mock()
    MockSiteSettingsCls.return_value = MockSiteSettings
    MockContainerStorage = Mock()
    mock_cs_factory.return_value = MockContainerStorage

    # == No providers configured ==
    MockSiteSettings.get.return_value = None
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert providers.get_provider_id_for_container(container, cls) is None

    # == Site only ==
    MockSiteSettings.get.return_value = models.SiteSettings(center_gears=[], providers={'compute': site_provider_id})
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert providers.get_provider_id_for_container(container, cls) is site_provider_id

    # == Group ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group', 'providers': {'compute': group_provider_id}}
    )
    assert providers.get_provider_id_for_container(container, cls) is group_provider_id

    # == Project ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project', 'providers': {'compute': project_provider_id}},
        {'_id': 'group', 'providers': {'compute': group_provider_id}}
    )
    assert providers.get_provider_id_for_container(container, 'compute') is project_provider_id
