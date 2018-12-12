
def test_site_settings_update(as_admin, api_db):
    # Should start with empty state
    r = as_admin.get('/site/settings')
    assert r.ok
    assert r.json() == {}

    # Add center_gears
    r = as_admin.put('/site/settings', json={'center_gears': ['test-gear', 'afq-demo']})
    assert r.ok

    # Verify update
    r = as_admin.get('/site/settings')
    assert r.ok
    settings = r.json()
    assert settings['center_gears'] == ['test-gear', 'afq-demo']

    # Reset database
    api_db.singletons.update({'_id': 'site'}, {})


def test_site_settings_validation(as_admin):
    # No body
    r = as_admin.put('/site/settings')
    assert r.status_code == 400

    # Additional properties
    r = as_admin.put('/site/settings', json={'center_gears': [], 'foo':  1})
    assert r.status_code == 400

    # center_gears type
    r = as_admin.put('/site/settings', json={'center_gears': [1, 2, 3]})
    assert r.status_code == 400


def test_site_settings_authorization(as_public, as_user):
    body = {'center_gears': []}

    # No public access
    assert as_public.get('/site/settings').status_code == 403
    assert as_public.put('/site/settings', json=body).status_code == 403

    # User can read but not edit
    assert as_user.get('/site/settings').ok
    assert as_user.put('/site/settings', json=body).status_code == 403
