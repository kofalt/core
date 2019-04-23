import datetime
import re

import pytest
import requests_mock


def test_jwt_auth(config, as_drone, as_public, api_db):
    # try to login w/ unconfigured auth provider
    r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
    assert r.status_code == 400

    # inject ldap (jwt) auth config
    config['auth']['ldap'] = dict(
        verify_endpoint='http://ldap.test',
        check_ssl=False)

    uid = 'ldap@ldap.test'
    with requests_mock.Mocker() as m:
        # try to log in w/ ldap and invalid token (=code)
        m.post(config.auth.ldap.verify_endpoint, status_code=400)
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ ldap - pretend provider doesn't return mail
        m.post(config.auth.ldap.verify_endpoint, json={})
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ ldap - user not in db (yet)
        m.post(config.auth.ldap.verify_endpoint, json={'mail': uid})
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ ldap - user added but disabled
        assert as_drone.post('/users', json={
            '_id': uid, 'disabled': True, 'firstname': 'test', 'lastname': 'test'}).ok
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.status_code == 402

        # log in w/ ldap (also mock gravatar 404)
        m.head(re.compile('https://gravatar.com/avatar'), status_code=404)
        as_drone.put('/users/' + uid, json={'disabled': False})
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.ok
        assert 'gravatar' not in api_db.users.find_one({'_id': uid})['avatars']
        token = r.json['token']

        # access api w/ valid token
        r = as_public.get('', headers={'Authorization': token})
        assert r.ok

        # log in w/ ldap (now w/ existing gravatar)
        m.head(re.compile('https://gravatar.com/avatar'))
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.ok
        assert 'gravatar' in api_db.users.find_one({'_id': uid})['avatars']

        # clean up
        api_db.authtokens.delete_one({'_id': token})
        api_db.users.delete_one({'_id': uid})

def test_jwt_auth_with_mail_format(config, as_drone, as_public, api_db):
    # inject ldap (jwt) auth config
    config['auth']['ldap'] = dict(
        verify_endpoint='http://ldap.test',
        mail_format='{uid}@scitran.edu',
        check_ssl=False)

    uid = 'ldapuser'
    email = 'ldapuser@scitran.edu'
    api_db.users.delete_one({'_id': email})
    with requests_mock.Mocker() as m:
        # try to log in w/ ldap - pretend provider doesn't return uid
        m.post(config.auth.ldap.verify_endpoint, json={'mail': 'ldap@ldap.test'})
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ ldap - user not in db (yet)
        m.post(config.auth.ldap.verify_endpoint, json={'uid': uid, 'mail': 'ldap@ldap.test'})
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ ldap
        assert as_drone.post('/users', json={'_id': email, 'firstname': 'test', 'lastname': 'test'}).ok

        m.head(re.compile('https://gravatar.com/avatar'), status_code=404)
        r = as_public.post('/login', json={'auth_type': 'ldap', 'code': 'test'})
        assert r.ok
        token = r.json['token']

        # Verify UID & Email
        user = api_db.users.find_one({'_id': email})
        assert 'gravatar' not in user['avatars']
        assert user['_id'] == email
        assert user['email'] == email

        # clean up
        api_db.authtokens.delete_one({'_id': token})
        api_db.users.delete_one({'_id': email})

def test_cas_auth(config, as_drone, as_public, api_db):
    # try to login w/ unconfigured auth provider
    r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
    assert r.status_code == 400

    # inject cas auth config
    config['auth']['cas'] = dict(
        service_url_state='?state=cas',
        auth_endpoint='http://cas.test/cas/login',
        verify_endpoint='http://cas.test/cas/serviceValidate',
        namespace='cas.test',
        display_string='CAS Auth')

    username = 'cas'
    uid = username+'@'+config.auth.cas.namespace

    with requests_mock.Mocker() as m:
        # try to log in w/ cas and invalid token (=code)
        m.get(config.auth.cas.verify_endpoint, status_code=400)
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.status_code == 401

        xml_response_unsuccessful = """
        <cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
            <cas:authenticationFailure>
            </cas:authenticationFailure>
        </cas:serviceResponse>
        """

        # try to log in w/ cas - pretend provider doesn't return with success
        m.get(config.auth.cas.verify_endpoint, content=xml_response_unsuccessful)
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.status_code == 401

        xml_response_malformed = """
        <cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
            <cas:authenticationSuccess>
                <cas:bad_key>cas</cas:bad_key>
            </cas:authenticationSuccess>
        </cas:serviceResponse>
        """

        # try to log in w/ cas - pretend provider doesn't return valid username response
        m.get(config.auth.cas.verify_endpoint, content=xml_response_malformed)
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.status_code == 401

        xml_response_successful = """
        <cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
            <cas:authenticationSuccess>
                <cas:user>cas</cas:user>
            </cas:authenticationSuccess>
        </cas:serviceResponse>
        """

        # try to log in w/ cas - user not in db (yet)
        m.get(config.auth.cas.verify_endpoint, content=xml_response_successful)
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ cas - user added but disabled
        assert as_drone.post('/users', json={
            '_id': uid, 'disabled': True, 'firstname': 'test', 'lastname': 'test'}).ok
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.status_code == 402

        # log in w/ cas (also mock gravatar 404)
        m.head(re.compile('https://gravatar.com/avatar'), status_code=404)
        as_drone.put('/users/' + uid, json={'disabled': False})
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.ok
        assert 'gravatar' not in api_db.users.find_one({'_id': uid})['avatars']
        token = r.json['token']

        # access api w/ valid token
        r = as_public.get('', headers={'Authorization': token})
        assert r.ok

        # log in w/ cas (now w/ existing gravatar)
        m.head(re.compile('https://gravatar.com/avatar'))
        r = as_public.post('/login', json={'auth_type': 'cas', 'code': 'test'})
        assert r.ok
        assert 'gravatar' in api_db.users.find_one({'_id': uid})['avatars']

        # clean up
        api_db.authtokens.delete_one({'_id': token})
        api_db.users.delete_one({'_id': uid})


def test_google_auth(config, as_drone, as_public, api_db):
    # inject google auth client_secret into config
    config['auth']['google']['client_secret'] = 'test'

    # try to access api w/ invalid session token
    r = as_public.get('', headers={'Authorization': 'test'})
    assert r.status_code == 401

    # try to login w/o code/auth_type
    r = as_public.post('/login', json={})
    assert r.status_code == 400

    # try to login w/ invalid auth_type
    r = as_public.post('/login', json={'auth_type': 'test', 'code': 'test'})
    assert r.status_code == 400

    uid = 'google@google.test'
    with requests_mock.Mocker() as m:
        # try to log in w/ google and invalid code
        m.post(config.auth.google.token_endpoint, status_code=400)
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ google and invalid token
        m.post(config.auth.google.token_endpoint, json={'access_token': 'test'})
        m.get(config.auth.google.id_endpoint, status_code=400)
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ google - pretend provider doesn't return email
        m.get(config.auth.google.id_endpoint, json={})
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ google - user not in db (yet)
        m.get(config.auth.google.id_endpoint, json={'email': uid})
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ google - user added but disabled
        as_drone.post('/users', json={
            '_id': uid, 'disabled': True, 'firstname': 'test', 'lastname': 'test'}).ok
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ google - invalid refresh token (also mock gravatar 404)
        as_drone.put('/users/' + uid, json={'disabled': False})
        m.head(re.compile('https://gravatar.com/avatar'), status_code=404)
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.status_code == 401
        assert 'gravatar' not in api_db.users.find_one({'_id': uid})['avatars']

        # log in (now w/ existing gravatar)
        m.head(re.compile('https://gravatar.com/avatar'))
        m.post(config.auth.google.token_endpoint, json={
            'access_token': 'test', 'expires_in': 60, 'refresh_token': 'test'})
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        assert r.ok
        assert 'gravatar' in api_db.users.find_one({'_id': uid})['avatars']
        token_1 = r.json['token']

        # access api w/ valid token
        r = as_public.get('', headers={'Authorization': token_1})
        assert r.ok

        # try to access api w/ expired token - provider fails to refresh token
        api_db.authtokens.update_one({'_id': token_1}, {'$set':
            {'expires': datetime.datetime.now() - datetime.timedelta(seconds=1)}})
        m.post(config.auth.google.refresh_endpoint, status_code=400)
        r = as_public.get('', headers={'Authorization': token_1})
        assert r.status_code == 401
        assert not api_db.authtokens.find({'_id': token_1}).count()

        # access api w/ expired token - test refresh
        m.post(config.auth.google.token_endpoint, json={
            'access_token': 'test', 'expires_in': -1, 'refresh_token': 'test'})
        r = as_public.post('/login', json={'auth_type': 'google', 'code': 'test'})
        token_2 = r.json['token']
        m.post(config.auth.google.refresh_endpoint, json={'access_token': 'test', 'expires_in': 60})
        r = as_public.get('', headers={'Authorization': token_2})
        assert r.ok

        # try to access api w/ expired token but w/o persisted refresh_token
        api_db.authtokens.update_one({'_id': token_2}, {'$set':
            {'expires': datetime.datetime.now() - datetime.timedelta(seconds=1)}})
        api_db.refreshtokens.delete_one({'uid': uid})
        r = as_public.get('', headers={'Authorization': token_2})
        assert r.status_code == 401

        # clean up
        api_db.authtokens.delete_one({'_id': token_2})
        api_db.users.delete_one({'_id': uid})

    # try to logout w/o auth headers
    r = as_public.post('/logout')
    assert r.status_code == 401


def test_wechat_auth(config, as_drone, as_public, api_db):
    # inject wechat auth config
    config['auth']['wechat'] = dict(
        client_id='test',
        client_secret='test',
        token_endpoint='http://wechat.test/token',
        refresh_endpoint='http://wechat.test/refresh')

    uid = 'wechat@wechat.test'
    with requests_mock.Mocker() as m:
        # try to log in w/ wechat and invalid code
        m.post(config.auth.wechat.token_endpoint, status_code=400)
        r = as_public.post('/login', json={'auth_type': 'wechat', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ wechat - pretend provider doesn't return openid
        m.post(config.auth.wechat.token_endpoint, json={})
        r = as_public.post('/login', json={'auth_type': 'wechat', 'code': 'test'})
        assert r.status_code == 401

        # try to log in w/ wechat - user not in db (yet)
        m.post(config.auth.wechat.token_endpoint, json={'openid': 'test'})
        r = as_public.post('/login', json={'auth_type': 'wechat', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ wechat w/o regitration (same error as above, no user associated w/ openid)
        assert as_drone.post('/users', json={
            '_id': uid, 'firstname': 'test', 'lastname': 'test'}).ok
        r = as_public.post('/login', json={'auth_type': 'wechat', 'code': 'test'})
        assert r.status_code == 402

        # try to log in w/ wechat w/ invalid regitration code
        r = as_public.post('/login', json={
            'auth_type': 'wechat', 'code': 'test', 'registration_code': 'test'})
        assert r.status_code == 402

        # generate registration code
        r = as_drone.post('/users/' + uid + '/reset-registration')
        assert r.ok
        assert 'registration_code' in api_db.users.find_one({'_id': uid})['wechat']
        regcode_1 = r.json['registration_code']

        # try to log in w/ wechat w/o refresh token from provider
        r = as_public.post('/login', json={
            'auth_type': 'wechat', 'code': 'test', 'registration_code': regcode_1})
        assert r.status_code == 401
        assert 'openid' in api_db.users.find_one({'_id': uid})['wechat']
        assert 'registration_code' not in api_db.users.find_one({'_id': uid})['wechat']

        # try to log in w/ wechat w/o openid already existing in db
        m.post(config.auth.wechat.token_endpoint, json={'openid': 'test', 'refresh_token': 'test'})
        regcode_2 = as_drone.post('/users/' + uid + '/reset-registration').json['registration_code']
        r = as_public.post('/login', json={
            'auth_type': 'wechat', 'code': 'test', 'registration_code': regcode_2})
        assert r.status_code == 402

        # log in w/ wechat
        m.post(config.auth.wechat.token_endpoint, json={
            'openid': 'test', 'refresh_token': 'test', 'access_token': 'test', 'expires_in': 60})
        api_db.users.update_one({'_id': uid}, {'$unset': {'wechat.openid': ''}})
        r = as_public.post('/login', json={
            'auth_type': 'wechat', 'code': 'test', 'registration_code': regcode_2})
        assert r.ok
        token_1 = r.json['token']

        # access api w/ valid token
        r = as_public.get('', headers={'Authorization': token_1})
        assert r.ok

        # try to access api w/ expired token - provider fails to refresh token
        api_db.authtokens.update_one({'_id': token_1}, {'$set':
            {'expires': datetime.datetime.now() - datetime.timedelta(seconds=1)}})
        m.post(config.auth.wechat.refresh_endpoint, status_code=400)
        r = as_public.get('', headers={'Authorization': token_1})
        assert r.status_code == 401
        assert not api_db.authtokens.find({'_id': token_1}).count()

        # access api w/ expired token - test refresh
        m.post(config.auth.wechat.token_endpoint, json={
            'openid': 'test', 'refresh_token': 'test', 'access_token': 'test', 'expires_in': -1})
        r = as_public.post('/login', json={'auth_type': 'wechat', 'code': 'test'})
        token_2 = r.json['token']
        m.post(config.auth.wechat.refresh_endpoint, json={'access_token': 'test', 'expires_in': 60})
        r = as_public.get('', headers={'Authorization': token_2})
        assert r.ok

        # try to log in w/ ldap - user disabled
        assert as_drone.put('/users/' + uid, json={'disabled': True}).ok
        r = as_public.post('/login', json={'auth_type': 'wechat', 'code': 'test'})
        assert r.status_code == 402

        # clean up
        api_db.authtokens.delete_one({'_id': token_2})
        api_db.users.delete_one({'_id': uid})

def test_saml_auth(config, as_drone, as_public, api_db):
    # try to login w/ unconfigured auth provider
    r = as_public.get('/login/saml')
    assert r.status_code == 400

    # inject saml auth config
    config['auth']['saml'] = dict(
        auth_endpoint='http://saml.test/secure/login/saml',
        verify_endpoint='http://saml.test/Shibboleth.sso/Session',
        refresh_rate=300,
        display_string='SAML Auth',
        uid_key_name='mail')


    uid = 'saml_uid@saml.test'

    with requests_mock.Mocker() as m:
        # try to log in w/ saml and no shibboleth cookie
        r = as_public.get('/login/saml')
        assert r.status_code == 401

        # try to log in w/ saml and no shibboleth session
        # (Shibboleth's /Session endpoint returns empty json
        #  when there is no active session for the supplied cookie)
        m.get(config.auth.saml.verify_endpoint, json={})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 401

        # valid session but no attributes key
        m.get(config.auth.saml.verify_endpoint, json={'some': 'data'})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 401

        # valid session but attributes key is empty
        m.get(config.auth.saml.verify_endpoint, json={'some': 'data', 'attributes': []})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 401

        # valid session but attributes list does not contain "mail"
        m.get(config.auth.saml.verify_endpoint, json={'some': 'data', 'attributes': [{'name': 'bob', 'values': ['test']}]})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 401

        # valid session but attributes "values" for "mail" is empty
        m.get(config.auth.saml.verify_endpoint, json={'some': 'data', 'attributes': [{'name': 'mail', 'values': []}]})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 401

        # try to log in w/ saml - user added but disabled
        assert as_drone.post('/users', json={
            '_id': uid, 'disabled': True, 'firstname': 'test', 'lastname': 'test'}).ok
        m.get(config.auth.saml.verify_endpoint, json={'attributes': [{'name': 'mail', 'values': [uid]}]})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 402

        # log in w/ saml (also mock gravatar 404)
        m.head(re.compile('https://gravatar.com/avatar'), status_code=404)
        as_drone.put('/users/' + uid, json={'disabled': False})
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 302
        assert 'gravatar' not in api_db.users.find_one({'_id': uid})['avatars']
        assert api_db.refreshtokens.find_one({'uid': uid, 'auth_type': 'saml'})

        # log in w/ saml (now w/ existing gravatar)
        m.head(re.compile('https://gravatar.com/avatar'))
        r = as_public.get('/login/saml', cookies={'_shibsession_test': 'test_cookie_content'})
        assert r.status_code == 302
        assert 'gravatar' in api_db.users.find_one({'_id': uid})['avatars']

        # clean up
        api_db.authtokens.delete_many({'uid': uid})
        api_db.users.delete_one({'_id': uid})
