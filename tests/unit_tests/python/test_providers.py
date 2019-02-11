import datetime

import bson
import pytest

from api.web import errors
from api.site.models import Provider, ProviderClass
from api.site.mappers import ProviderMapper
from api.site import providers

origin = { 'type': 'user', 'id': 'user@test.com' }
config = { 'key': 'value' }

def _make_provider(cls=ProviderClass.compute):
    return Provider(cls, 'gcloud', 'GCloud Test', origin, config)

# === Model Tests ===
def test_provider_delattr():
    provider = _make_provider()
    del provider.config
    assert provider.config is None
    assert 'config' not in provider.to_dict()
    del provider.config

# === Mapper Tests ===
def test_provider_mapper_insert(api_db):
    mapper = ProviderMapper(api_db)

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
        assert doc['provider_type'] == 'gcloud'
        assert doc['label'] == 'GCloud Test'
        assert doc['origin'] == origin
        assert doc['config'] == config

    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_find(api_db):
    # Insert provider
    mapper = ProviderMapper(api_db)
    provider = _make_provider()
    provider_id = mapper.insert(provider)

    try:
        # Find by arbitrary object id (None)
        result = mapper.find(bson.ObjectId())
        assert result is None

        # Find by ObjectId
        result = mapper.find(provider_id)
        assert result is not None
        assert result.provider_id == provider_id
        assert result.to_dict() == provider.to_dict()

        # Find by string
        result = mapper.find(str(provider_id))
        assert result.to_dict() == provider.to_dict()
    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_patch(api_db):
    # Insert provider
    mapper = ProviderMapper(api_db)
    provider = _make_provider()
    provider_id = mapper.insert(provider)

    try:
        config2 = { 'new_key': 'new_value' }
        mapper.patch(provider_id, {'label': 'My Provider', 'config': config2})

        # Find by ObjectId
        result = mapper.find(provider_id)

        assert result.modified >= result.created
        assert result.label == 'My Provider'
        assert result.config == config2
        assert result.provider_class == ProviderClass.compute
    finally:
        # Cleanup
        api_db.providers.remove({'_id': provider_id})

def test_provider_mapper_find_by_type(api_db):
    compute_provider = _make_provider()
    storage_provider = _make_provider(cls=ProviderClass.storage)

    mapper = ProviderMapper(api_db)
    cid = mapper.insert(compute_provider)
    sid = mapper.insert(storage_provider)

    try:
        results = list(mapper.find_by_class(ProviderClass.storage))
        assert len(results) == 1
        assert results[0].to_dict() == storage_provider.to_dict()

        results = list(mapper.find_by_class('compute'))
        assert len(results) == 1
        assert results[0].to_dict() == compute_provider.to_dict()

        results = list(mapper.find_by_class('none'))
        assert len(results) == 0

    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

# === Factory Tests ===
def test_provider_factory_error():
    # Non-existent storage
    with pytest.raises(ValueError):
        provider = providers.create_provider(ProviderClass.storage, 'garbage', {})

def test_provider_factory_static_compute():
    config = {'key': 'value'}

    # Static compute
    provider = providers.create_provider(ProviderClass.compute, 'static', config)
    assert provider is not None
    assert provider.config == config

    with pytest.raises(errors.APIValidationException):
        provider.validate_config()

    provider.config = {}
    provider.validate_config()  # Only empty config is valid for static

# === Repository Tests ===
def test_provider_repository_insert_and_update(api_db):
    # Invalid provider type
    provider = Provider(ProviderClass.storage, 'garbage', 'Label', origin, config)
    with pytest.raises(errors.APIValidationException):
        providers.insert_provider(provider)

    # Invalid provider config
    provider = Provider(ProviderClass.compute, 'static', 'Label', origin, config)
    with pytest.raises(errors.APIValidationException):
        providers.insert_provider(provider)

    # Valid provider config
    provider = Provider(ProviderClass.compute, 'static', 'Label', origin, {})
    provider_id = providers.insert_provider(provider)
    assert provider_id is not None

    try:
        # Load from data store
        mapper = ProviderMapper()
        result = mapper.find(provider_id)
        assert result.to_dict() == provider.to_dict()

        # Try to update non-existent
        with pytest.raises(errors.APINotFoundException):
            providers.update_provider(bson.ObjectId(), {'label': 'New Label'})

        # Try to update provider class
        with pytest.raises(errors.InputValidationException):
            providers.update_provider(str(provider_id), {'provider_class': 'storage'})

        # Try to update provider type
        with pytest.raises(errors.InputValidationException):
            providers.update_provider(str(provider_id), {'provider_type': 'garbage'})

        # Try to set invalid config
        with pytest.raises(errors.APIValidationException):
            providers.update_provider(provider_id, {'config': {'x':'y'}})

        # Successful update
        providers.update_provider(provider_id, {'label': 'New Label', 'config': {}})

        result = mapper.find(provider_id)
        assert result.config == {}
        assert result.label == 'New Label'
    finally:
        api_db.providers.remove({'_id': provider_id})

def test_provider_repository_load(api_db):
    compute_provider = _make_provider()
    storage_provider = _make_provider(cls=ProviderClass.storage)

    mapper = ProviderMapper()
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

        # Load by type
        results = list(providers.get_providers_by_class('compute'))
        assert len(results) == 1
        assert results[0].to_dict() == expected

        # Load just provider config
        result = providers.get_provider_config(cid)
        assert result == compute_provider.config
    finally:
        # Cleanup
        api_db.providers.remove({'_id': cid})
        api_db.providers.remove({'_id': sid})

