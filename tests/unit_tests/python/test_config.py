import copy
import datetime
import json
import re

import api.config

def test_get_feature():
    assert api.config.get_feature('job_tickets')
    assert api.config.get_feature('does_not_exist') is None
    assert api.config.get_feature('does_not_exist', True) == True

def test_apply_env_variables(mocker, tmpdir):
    auth_file, auth_content = 'auth_config.json', {'auth': {'test': 'test'}}
    tmpdir.join(auth_file).write(json.dumps(auth_content))
    mocker.patch('os.environ', {
        'SCITRAN_AUTH_CONFIG_FILE': str(tmpdir.join(auth_file)),
        'SCITRAN_TEST_TRUE': 'true',
        'SCITRAN_TEST_FALSE': 'false',
        'SCITRAN_TEST_NONE': 'none',
        'SCITRAN_SITE_UPLOAD_MAXIMUM_BYTES': '10',
        'FLYWHEEL_FEATURE_TRUE': 'true',
        'FLYWHEEL_FEATURE_FALSE': 'false',
        'FLYWHEEL_FEATURE_NONE': 'none',
        'FLYWHEEL_FEATURE_SUBJECTS_VIEW': 'why not'})

    config = {
        'auth': {'initial': 'auth'},
        'test': {'true': '', 'false': '', 'none': ''},
        'site': {'upload_maximum_bytes': '10737418240'},
        'features': {'test': True, 'true': False}}

    expected_features = {
        'test': True,
        'true': True,
        'false': False,
        'none': 'none',
        'subjects_view': 'why not'
    }

    api.config.apply_env_variables(config)
    assert config == {
        'auth': {'test': 'test'},
        'test': {'true': True, 'false': False, 'none': None},
        'site': {'upload_maximum_bytes': '10'},
        'features': expected_features}

    # Test that objects don't persist
    auth_file, auth_content = 'auth_config.json', {'auth': {'test2': 'test2'}}
    tmpdir.join(auth_file).write(json.dumps(auth_content))

    api.config.apply_env_variables(config)
    assert config == {
        'auth': {'test2': 'test2'},
        'test': {'true': True, 'false': False, 'none': None},
        'site': {'upload_maximum_bytes': '10'},
        'features': expected_features}

    # Test Default is used when no auth is provided
    auth_file, auth_content = 'auth_config.json', {}
    tmpdir.join(auth_file).write(json.dumps(auth_content))
    api.config.apply_env_variables(config)
    assert config['auth'].get('google')

    # Test setting a feature in storage
    with mocker.mock_module.patch('api.config.db') as db:
        features2 = copy.deepcopy(expected_features)
        features2['true'] = False
        features2['new_feature'] = 'test_value'
        db.singletons.find_one.return_value = {
            'core': {'debug': False, 'log_level': 'info'},
            'auth': {'test': 'test'},
            'test': {'true': True, 'false': False, 'none': None},
            'site': {'upload_maximum_bytes': '10'},
            'features': features2}
        api.config.__last_update = datetime.datetime.min

        try:
            result = api.config.get_config()
            assert result['features']['new_feature'] == 'test_value'
            assert not result['features']['true']
        finally:
            api.config.__last_update = datetime.datetime.min
    # restore original config
    api.config.get_config()

def test_create_or_recreate_ttl_index(mocker):
    db = mocker.patch('api.config.db')
    collection, index_id, index_name, ttl = 'collection', 'timestamp_1', 'timestamp', 1

    # create - collection not in collection_names
    db.collection_names.return_value = []
    api.config.create_or_recreate_ttl_index(collection, index_name, ttl)
    db.collection_names.assert_called_with()
    db[collection].create_index.assert_called_with(index_name, expireAfterSeconds=ttl)
    db[collection].create_index.reset_mock()

    # create - index doesn't exist
    db.collection_names.return_value = [collection]
    db[collection].index_information.return_value = {}
    api.config.create_or_recreate_ttl_index(collection, index_name, ttl)
    db[collection].create_index.assert_called_with(index_name, expireAfterSeconds=ttl)
    db[collection].create_index.reset_mock()

    # skip - index exists and matches
    db[collection].index_information.return_value = {index_id: {'key': [[index_name]], 'expireAfterSeconds': ttl}}
    api.config.create_or_recreate_ttl_index(collection, index_name, ttl)
    assert not db[collection].create_index.called

    # recreate - index exists but doesn't match
    db[collection].create_index.reset_mock()
    db[collection].index_information.return_value = {index_id: {'key': [[index_name]], 'expireAfterSeconds': 10}}
    api.config.create_or_recreate_ttl_index(collection, index_name, ttl)
    db[collection].drop_index.assert_called_with(index_id)
    db[collection].create_index.assert_called_with(index_name, expireAfterSeconds=ttl)

def test_signed_urls():
    regex = re.compile("remove_me")

    #We should assume our tests start with a valid state
    api.config.db.providers.remove({'label': regex})
    api.config.__last_update = datetime.datetime(2000, 1, 1)
    assert api.config.get_config()['features']['signed_url'] == False

    # One OSFS is assumed to be local storage
    api.config.db.providers.insert({'label': 'remove_me', 'provider_class': 'storage', 'provider_type': 'osfs'})
    assert api.config.get_config()['features']['signed_url'] == False

    # Lets add a signed url storage provider to trigger signed_url boolean true
    api.config.db.providers.insert({'label': 'remove_me_signed', 'provider_class': 'storage', 'provider_type': 'aws'})
    api.config.__last_update = datetime.datetime(2000, 1, 1)
    assert api.config.get_config()['features']['signed_url'] == True

    # Multiple signed url providers is still true
    api.config.db.providers.insert({'label': 'remove_me_signed_gc', 'provider_class': 'storage', 'provider_type': 'gc'})
    api.config.__last_update = datetime.datetime(2000, 1, 1)
    assert api.config.get_config()['features']['signed_url'] == True

    # Signed with only one gc provider
    api.config.db.providers.remove({'label': 'remove_me_signed'})
    api.config.__last_update = datetime.datetime(2000, 1, 1)
    assert api.config.get_config()['features']['signed_url'] == True
    api.config.db.providers.insert({'label': 'remove_me_signed', 'provider_class': 'storage', 'provider_type': 'aws'})

    # The second osfs will render signed urls False
    api.config.db.providers.insert({'label': 'remove_me_2', 'provider_class': 'storage', 'provider_type': 'osfs'})
    api.config.__last_update = datetime.datetime(2000, 1, 1)
    assert api.config.get_config()['features']['signed_url'] == False


    #Clean up our providers
    api.config.db.providers.remove({'label': regex})
