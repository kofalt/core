import bson

VALID_PROVIDER = {
    'provider_class': 'compute',
    'provider_type': 'static',
    'label': 'MyProvider',
    'config': {},
    'creds': {}
}
VALID_STORAGE_PROVIDER = {
    'provider_class': 'storage',
    'provider_type': 'local',
    'label': 'MyStorageProvider',
    'config': {'path': '/var'},
    'creds': {}
}

def test_providers_initial_state(as_user, with_site_settings, api_db):

    r = as_user.get('/site/providers')
    assert r.ok

    static_provider_id = None
    for provider in r.json():
        if (provider['provider_class'] == 'compute' and
            provider['label'] == 'StaticCompute'):
            static_provider_id = provider['_id']

    assert static_provider_id is not None

    r = as_user.get('/site/settings')
    assert r.ok
    site_settings = r.json()

    assert site_settings.get('providers', {}).get('compute') == static_provider_id

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
        'creds': {}
    })
    assert r.status_code == 422

    # Unknown provider type
    r = as_admin.post('/site/providers', json={
        'provider_class': 'other',
        'provider_type': 'static',
        'label': 'Label',
        'config': {},
        'creds': {}
    })
    assert r.status_code == 400  # Validated by enum type in schema

    # Validate static configuration
    r = as_admin.post('/site/providers', json={
        'provider_class': 'compute',
        'provider_type': 'static',
        'label': 'Label',
        'config': {'value': 'something'},
        'creds': {}
    })
    assert r.status_code == 422

    # No additional properties
    r = as_admin.post('/site/providers', json={
        'provider_class': 'compute',
        'provider_type': 'static',
        'label': 'Label',
        'config': {},
        'creds': {},
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
        assert r_provider['config'] == {}
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
        assert r_provider['config'] == {}

        r = as_user.get('/site/providers/' + provider_id)
        assert r.ok
        assert r.json() == r_provider

        r = as_admin.get('/site/providers?class=compute')
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

    r = as_admin.post('/site/providers', json=VALID_STORAGE_PROVIDER)
    assert r.ok
    storage_provider_id = r.json()['_id']

    try:
        r = as_public.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        r = as_user.get('/site/providers/' + provider_id + '/config')
        assert r.status_code == 403

        r = as_admin.get('/site/providers/' + provider_id + '/config')
        assert r.ok
        assert r.json() == {}

        r = as_root.get('/site/providers/' + provider_id + '/config')
        assert r.ok
        assert r.json() == {}

        r = as_drone.get('/site/providers/' + provider_id + '/config')
        assert r.ok
        assert r.json() == {}

        # create device
        r = as_root.post('/devices', json={'type': 'cloud-scale'})
        assert r.ok
        device_id = r.json()['_id']

        r = as_admin.get('/devices/' + device_id)
        assert r.ok
        device_key = r.json()['key']

        # Get config as valid device
        as_device = as_public
        as_device.headers.update({'Authorization': 'scitran-user {}'.format(device_key)})

        r = as_device.get('/site/providers/' + provider_id + '/config')
        assert r.ok
        # Static compute has no config nor creds but we should at least get the same unredacted structure
        assert r.json() == {'creds': {}, 'config': {}}

        # Still can't get storage config...
        r = as_device.get('/site/providers/' + storage_provider_id + '/config')
        assert r.status_code == 403

    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})
        api_db.providers.remove({'_id': bson.ObjectId(storage_provider_id)})

        # delete device
        if device_id is not None:
            assert as_root.delete('/devices/' + device_id).ok

def test_site_providers(api_db, data_builder, as_user, as_admin, with_site_settings):
    # Create a static compute provider
    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']

    try:
        r = as_admin.get('/site/settings')
        site_compute_provider_id = r.json()['providers']['compute']

        # Cannot override providers as site admin
        update = {'providers': {'compute': provider_id}}
        r = as_admin.put('/site/settings', json=update)
        assert r.status_code == 422

        # NOOP:
        update = {'providers': {'compute': site_compute_provider_id}}
        r = as_admin.put('/site/settings', json=update)
        assert r.ok

        # Can not remove all site providersP:
        update = {'providers': {}}
        r = as_admin.put('/site/settings', json=update)
        assert not r.ok

    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})

def test_group_providers(api_db, data_builder, as_user, as_admin):
    # Create a static compute provider
    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']

    try:
        # NOTE: Exhaustive validation is done in unit testing
        # of validate_provider_links

        # Create a new group
        group = data_builder.create_group(providers={})
        # Sets no compute provider
        r = as_user.get('/users/self')
        assert r.ok
        user = r.json()

        # Add an permission to the group
        user = {'access': 'admin', '_id': user['_id']}
        r = as_admin.post('/groups/' + group + '/permissions', json=user)
        assert r.ok

        # Try to set provider as group admin user (should 403)
        update = {'providers': {'compute': provider_id}}
        r = as_user.put('/groups/' + group, json=update)
        assert r.status_code == 403

        # Can set providers as site admin
        r = as_admin.put('/groups/' + group, json=update)
        assert r.ok

        #Can not change provider even as site admin
        new_compute = data_builder.create_compute_provider()
        update = {'providers': {'compute': new_compute}}
        r = as_admin.put('/groups/' + group, json=update)
        assert r.status_code == 422

        # Get the group
        r = as_admin.get('/groups/' + group)
        assert r.ok
        assert r.json()['providers'] == {'compute': provider_id}

        # Now create a group with initial providers
        group2 = data_builder.create_group(providers={'compute': provider_id})
        r = as_admin.get('/groups/' + group2)
        assert r.ok
        assert r.json()['providers'] == {'compute': provider_id}

    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})

def test_project_providers(api_db, data_builder, as_user, as_admin):
    # Create a static compute provider
    r = as_admin.post('/site/providers', json=VALID_PROVIDER)
    assert r.ok
    provider_id = r.json()['_id']

    try:
        # NOTE: Exhaustive validation is done in unit testing
        # of validate_provider_links

        # Create a new project, if you dont specify providers they are added by default
        project = data_builder.create_project(providers={})

        # Set the compute provider
        r = as_user.get('/users/self')
        assert r.ok
        user = r.json()

        # Add an permission to the project
        user = {'access': 'admin', '_id': user['_id']}
        r = as_admin.post('/projects/' + project + '/permissions', json=user)
        assert r.ok

        # Try to set provider as project admin user, NOT allowed even if not set previously
        update = {'providers': {'compute': provider_id}}
        r = as_user.put('/projects/' + project, json=update)
        assert r.status_code == 403

        # Can change provider on inital set
        new_compute = data_builder.create_compute_provider()
        update = {'providers': {'compute': new_compute}}
        r = as_admin.put('/projects/' + project, json=update)
        assert r.status_code == 200
        # Get the project
        r = as_admin.get('/projects/' + project)
        assert r.ok
        assert r.json()['providers'] == {'compute': new_compute}

        # Can not change provider even as admin once its set
        new_compute2 = data_builder.create_compute_provider()
        update = {'providers': {'compute': new_compute2}}
        r = as_admin.put('/projects/' + project, json=update)
        assert r.status_code == 422

        # Now create a project with initial providers
        project2 = data_builder.create_project(providers={'compute': provider_id})
        r = as_admin.get('/projects/' + project2)
        assert r.ok
        assert r.json()['providers']['compute'] == provider_id

        # Can't set provider on subject/session
        r = as_admin.post('/subjects', json={'project': project, 'code': 'subject2', 'providers': {'compute': provider_id}})
        assert r.status_code == 400
        r = as_admin.post('/sessions', json={'project': project, 'label': 'session2', 'providers': {'compute': provider_id}})
        assert r.status_code == 400

    finally:
        api_db.providers.remove({'_id': bson.ObjectId(provider_id)})


def test_provider_selection_user(data_builder, file_form, as_user, as_admin, api_db, with_site_settings, second_storage_provider):

    site_storage = str(api_db.singletons.find({'_id': 'site'})[0]['providers']['storage'])
    group = data_builder.create_group()
    project = data_builder.create_project(group=group)
    session = data_builder.create_session()

    # Add user to project
    uid = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': uid, 'access': 'admin'})
    assert r.ok

    # try to upload a file and verify site provider
    r = as_user.post('/projects/' + project + '/files', files=file_form('upload-test.csv'))
    assert r.ok
    files = r.json()
    assert len(files) == 1
    assert files[0]['name'] == 'upload-test.csv'
    assert files[0]['provider_id'] == site_storage

    # User project with provider as non site provider
    project = data_builder.create_project(providers={'storage': second_storage_provider})
    uid = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': uid, 'access': 'admin'})
    assert r.ok
    r = as_user.post('/projects/' + project + '/files', files=file_form('upload-test2.csv'))
    assert r.ok
    files = r.json()
    assert len(files) == 1
    assert files[0]['name'] == 'upload-test2.csv'
    assert files[0]['provider_id'] == second_storage_provider


    # Inhert the provider settings from the parent group
    group = data_builder.create_group(providers={'storage': second_storage_provider})
    project = data_builder.create_project(group=group)
    uid = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': uid, 'access': 'admin'})
    assert r.ok
    r = as_user.post('/projects/' + project + '/files', files=file_form('upload-test3.csv'))
    assert r.ok
    files = r.json()
    assert len(files) == 1
    assert files[0]['name'] == 'upload-test3.csv'
    assert files[0]['provider_id'] == second_storage_provider


    # Revert provider settings to verify site provider is selected
    # Providers are inherited on create so remove from both containers
    api_db.groups.update_one({"_id": group}, {'$set': {'providers': {}}})
    api_db.projects.update_one({"_id": bson.ObjectId(project)}, {'$set': {'providers': {}}})
    r = as_user.post('/projects/' + project + '/files', files=file_form('upload-test4.csv'))
    assert r.ok
    files = r.json()
    assert len(files) == 1
    assert files[0]['name'] == 'upload-test4.csv'
    assert files[0]['provider_id'] == site_storage

def test_provider_selection_job(data_builder, file_form, as_user, as_admin, api_db, with_site_settings, second_storage_provider):

    group = data_builder.create_group()
    project = data_builder.create_project()
    acquisition = data_builder.create_acquisition()
    api_db.acquisitions.update({'_id': acquisition}, {'$set': {'parents': {'group': group, 'project': project}}})
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.txt')).ok

    site_storage = str(api_db.singletons.find({'_id': 'site'})[0]['providers']['storage'])

    job = data_builder.create_job(inputs={
        'test': {'type': 'acquisition', 'id': acquisition, 'name': 'test.txt'}
    })

    metadata = {
        'project':{
            'label': 'engine project test',
            'info': {'test': 'p'},
            'tags': ['one', 'two']
        },
        'session':{
            'label': 'engine session',
            'subject': {
                'code': 'engine subject',
                'sex': 'male',
                'age': 100000000000,
            },
            'info': {'test': 's', 'file.txt': 'Hello'},
            'tags': ['one', 'two']
        },
        'acquisition':{
            'label': 'engine acquisition',
            'timestamp': '2016-06-20T21:57:36+00:00',
            'info': {'test': 'a'},
            'files':[
                {
                    'name': 'one.csv',
                    'type': 'engine type 0',
                    'info': {'test': 'f1'}
                }
            ],
            'tags': ['one', 'two']
        }
    }

    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'filename_path':False},
        files=file_form('one.csv', 'folderA/two.csv', meta=metadata)
    )
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()
    found = False
    for file_ in a['files']:
        if file_['name'] == 'one.csv':
            found = True
            assert file_['provider_id'] == site_storage
            break
    assert found

    # Change the project provider so new files are not on site provider
    api_db.groups.update_one({"_id": group}, {'$set': {'providers.storage': bson.ObjectId(second_storage_provider)}})
    api_db.projects.update_one({"_id": project}, {'$set': {'providers.storage': bson.ObjectId(second_storage_provider)}})

    metadata['acquisition']['files'] = [
        {
            'name': 'two.csv',
            'type': 'engine type 0',
            'info': {'test': 'f2'}
        }
    ]
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'filename_path':False},
        files=file_form('two2.csv', meta=metadata)
    )
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()
    found = False
    for file_ in a['files']:
        if file_['name'] == 'two2.csv':
            if file_['provider_id'] == second_storage_provider:
                found = True
                break
    assert found


    # Specify provider on the group so new files are not on site provider
    api_db.groups.update_one({"_id": group}, {'$set': {'providers.storage': bson.ObjectId(second_storage_provider)}})
    api_db.projects.update_one({"_id": project}, {'$set': {'providers': {}}})
    metadata['acquisition']['files'] = [
        {
            'name': 'three.csv',
            'type': 'engine type 0',
            'info': {'test': 'f3'}
        }
    ]
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'filename_path':False},
        files=file_form('three.csv', meta=metadata)
    )
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()
    found = False
    for file_ in a['files']:
        if file_['name'] == 'three.csv':
            found = True
            assert file_['provider_id'] == second_storage_provider
            break
    assert found


    # Remove provider so  new files are again on site provider
    api_db.groups.update_one({"_id": group}, {'$set': {'providers': {}}})
    api_db.projectss.update_one({"_id": project}, {'$set': {'providers': {}}})
    metadata['acquisition']['files'] = [
        {
            'name': 'four.csv',
            'type': 'engine type 0',
            'info': {'test': 'f4'}
        }
    ]
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'filename_path':False},
        files=file_form('four.csv', meta=metadata)
    )
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()
    found = False
    for file_ in a['files']:
        if file_['name'] == 'four.csv':
            found = True
            assert file_['provider_id'] == site_storage
            break
    assert found
