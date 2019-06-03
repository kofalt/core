import requests_mock


def test_user_auth_token(config, as_user, as_public, api_db, mocker):
    # inject google auth client_secret into config
    config['auth']['google']['client_secret'] = 'test'

    # login required
    r = as_public.post('/users/self/tokens')
    assert r.status_code == 403
    # only google auth is supported
    r = as_user.post('/users/self/tokens', json={'code': 'test', 'auth_type': 'ldap'})
    assert r.status_code == 400

    with requests_mock.Mocker() as m:
        m.register_uri('GET', config.auth.google.verify_endpoint, json={'scope': 'email profile'})

        # try to add an invalid code
        m.post(config.auth.google.token_endpoint, status_code=400)
        r = as_user.post('/users/self/tokens', json={'code': 'test', 'auth_type': 'google'})
        assert r.status_code == 400

        # got back invalid access token
        m.post(config.auth.google.token_endpoint, json={'access_token': 'test'})
        m.get(config.auth.google.id_endpoint, status_code=400)
        r = as_user.post('/users/self/tokens', json={'code': 'test', 'auth_type': 'google'})
        assert r.status_code == 400

        validate_user_mock = mocker.patch(
            'api.auth.authproviders.GoogleOAuthProvider.validate_user')
        set_refresh_token_if_exists_mock = mocker.patch(
            'api.auth.authproviders.GoogleOAuthProvider.set_refresh_token_if_exists')

        m.post(config.auth.google.token_endpoint, json={
            'access_token': 'test', 'expires_in': 60})
        m.get(config.auth.google.id_endpoint, json={'email': 'test@test.com'})
        r = as_user.post('/users/self/tokens', json={'code': 'test', 'auth_type': 'google'})
        assert r.ok
        assert r.json['_id']
        assert not validate_user_mock.called
        assert not set_refresh_token_if_exists_mock.called
        token_id = r.json['_id']

        # test list, should not return access token
        r = as_public.get('/users/self/tokens')
        assert r.status_code == 403

        r = as_user.get('/users/self/tokens')
        assert r.ok
        token = r.json[0]
        assert sorted(token.keys()) == sorted(['_id', 'identity', 'auth_type'])

        # test get token endpoint, public user doesn't have access
        r = as_public.get('/users/self/tokens/' + token_id)
        assert r.status_code == 403

        # token not found
        r = as_user.get('/users/self/tokens/000000000000000000000000')
        assert r.status_code == 404

        # token expired, no refresh token specified so it is removed from db
        r = as_user.get('/users/self/tokens/' + token_id)
        assert r.status_code == 404

        m.post(config.auth.google.token_endpoint, json={
            'access_token': 'test', 'expires_in': 61, 'refresh_token': 'test'})
        r = as_user.post('/users/self/tokens', json={'code': 'test', 'auth_type': 'google'})
        assert r.ok
        token_id = r.json['_id']

        # token won't be renewed if more than 60 seconds left until it expires
        refresh_token_mock = mocker.patch(
            'api.auth.authproviders.GoogleOAuthProvider.refresh_token',
            return_value={'access_token': 'test_refreshed', 'expires_in': 60})
        r = as_user.get('/users/self/tokens/' + token_id)
        assert r.status_code == 200
        assert r.json['access_token'] == 'test'
        assert not refresh_token_mock.called

        m.post(config.auth.google.token_endpoint, json={
            'access_token': 'test', 'expires_in': 59, 'refresh_token': 'test'})
        r = as_user.post('/users/self/tokens', json={'code': 'test', 'auth_type': 'google'})
        assert r.ok
        token_id = r.json['_id']

        # will be refreshed at less than 60 seconds
        r = as_user.get('/users/self/tokens/' + token_id)
        assert r.status_code == 200
        assert r.json['access_token'] == 'test_refreshed'
        assert refresh_token_mock.called

        # revoke token
        revoke_token_mock = mocker.patch(
            'api.auth.authproviders.GoogleOAuthProvider.revoke_token')
        r = as_user.delete('/users/self/tokens/' + token_id)
        assert r.status_code == 200
        assert revoke_token_mock.called

        r = as_user.get('/users/self/tokens/' + token_id)
        assert r.status_code == 404
