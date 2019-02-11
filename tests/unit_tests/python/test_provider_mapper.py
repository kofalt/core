import datetime

import bson

from api.site.models import Provider, ProviderClass
from api.site.mappers import ProviderMapper

origin = { 'type': 'user', 'id': 'user@test.com' }
config = { 'key': 'value' }

def _make_provider(cls=ProviderClass.compute):
    return Provider(cls, 'gcloud', 'GCloud Test', origin, config)

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
