import bson

VALID_PROVIDER = {
    'provider_class': 'compute',
    'provider_type': 'static',
    'label': 'My Provider',
    'config': {},
}

def test_create_providers(api_db, as_admin, as_user, as_public):
    # Create and retrieve
    r = as_public.get('/site/providers')
    assert r.status_code == 403

    r = as_user.post('/site/providers', json=VALID_PROVIDER)
    assert r.status_code == 403

    r = as_public.post('/site/providers', json=VALID_PROVIDER)
    assert r.status_code == 403

    r = as_admin.post('/site/providers', json={})
    assert r.status_code == 400

    r = as_admin.post('/site/providers', json={'provider_class': 'compute'})
    assert r.status_code == 400

    # Unknown provider type
    r = as_admin.post('/site/providers', json={
        'provider_class': 'compute',
        'provider_type': 'other',
        'label': 'Label',
        'config': {},
    })
    assert r.status_code == 422

    # Unknown provider type
    r = as_admin.post('/site/providers', json={
        'provider_class': 'other',
        'provider_type': 'static',
        'label': 'Label',
        'config': {},
    })
    assert r.status_code == 400  # Validated by enum type in schema

    # Validate static configuration
    r = as_admin.post('/site/providers', json={
        'provider_class': 'compute',
        'provider_type': 'static',
        'label': 'Label',
        'config': {'value': 'something'},
    })
    assert r.status_code == 422

    # No additional properties
    r = as_admin.post('/site/providers', json={
        'provider_class': 'compute',
        'provider_type': 'static',
        'label': 'Label',
        'config': {},
        'extra': True,
    })
    assert r.status_code == 400

    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']

    try:
        r = as_admin.get('/site/providers/' + provider_id)
        assert r.ok
        r_provider = r.json()
        assert r_provider['provider_class'] == VALID_PROVIDER['provider_class']
        assert r_provider['provider_type'] == VALID_PROVIDER['provider_type']
        assert r_provider['label'] == VALID_PROVIDER['label']
        assert 'config' not in r_provider
    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})

def test_get_provider(api_db, as_admin, as_user, as_public):
    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']

    try:
        r = as_admin.get('/site/providers/' + provider_id)
        assert r.ok
        r_provider = r.json()
        assert r_provider['provider_class'] == VALID_PROVIDER['provider_class']
        assert r_provider['provider_type'] == VALID_PROVIDER['provider_type']
        assert r_provider['label'] == VALID_PROVIDER['label']
        assert 'config' not in r_provider

        r = as_user.get('/site/providers/' + provider_id)
        assert r.ok
        assert r.json() == r_provider

        r = as_admin.get('/site/providers?provider_class=compute')
        assert r.ok
        r_providers = r.json()
        assert len(r_providers) >= 1
        assert r_provider in r_providers

        for p in r_providers:
            assert p['provider_class'] == 'compute'

        r = as_user.get('/site/providers')
        assert r.ok
        r_providers = r.json()
        assert len(r_providers) >= 1
        assert r_provider in r_providers

        r = as_user.get('/site/providers?class=storage')
        assert r.ok
        assert r_provider not in r.json()
    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})

def test_update_provider(api_db, as_admin, as_user, as_public):
    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']

    try:
        r = as_user.put('/site/providers/' + provider_id, json={'label': 'Test'})
        assert r.status_code == 403

        r = as_public.put('/site/providers/' + provider_id, json={'label': 'Test'})
        assert r.status_code == 403

        # Cannot change provider type
        r = as_admin.put('/site/providers/' + provider_id, json={'provider_class': 'compute'})
        assert r.status_code == 422

        r = as_admin.put('/site/providers/' + provider_id, json={'provider_type': 'other'})
        assert r.status_code == 422

        # Invalid config
        r = as_admin.put('/site/providers/' + provider_id, json={'config': {'key': 'value'}})
        assert r.status_code == 422

        # Valid update
        r = as_admin.put('/site/providers/' + provider_id, json={'label': 'Test'})
        assert r.status_code == 200

        r = as_admin.get('/site/providers/' + provider_id)
        assert r.ok
        r_provider = r.json()
        assert r_provider['provider_class'] == VALID_PROVIDER['provider_class']
        assert r_provider['provider_type'] == VALID_PROVIDER['provider_type']
        assert r_provider['label'] == 'Test'
    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})

def test_get_provider_config(api_db, as_admin, as_user, as_public, as_drone, as_root):
    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']
    device_id = None

    try:
        r = as_public.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        r = as_user.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        r = as_admin.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        r = as_root.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        r = as_drone.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        # create device
        r = as_root.post('/devices', json={'type': 'cloud-scale'})
        assert r.ok
        device_id = r.json()['_id']

        r = as_admin.get('/devices/' + device_id)
        assert r.ok
        device_key = r.json()['key']

        # Get config as valid device
        api_db.providers.update({'_id': bson.ObjectId(provider_id)}, {'$set': {'config': {'top': 'secret'}}})

        as_device = as_public
        as_device.headers.update({'Authorization': 'scitran-user {}'.format(device_key)})

        r = as_device.get('/site/providers/' + provider_id + '/config')
        assert r.ok
        assert r.json() == {'top': 'secret'}

        # Still can't get storage config...
        api_db.providers.update({'_id': bson.ObjectId(provider_id)}, {'$set': {'provider_class': 'storage'}})
        r = as_device.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})

        # delete device
        if device_id is not None:
            assert as_root.delete('/devices/' + device_id).ok
