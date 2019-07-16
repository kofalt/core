import bson
import pytest

def test_project_create(mocker, data_builder, as_admin, api_db, with_site_settings):

    # Create new project via POST
    group = data_builder.create_group()
    r = as_admin.put('/groups/' + group, json={
        'editions': {'lab': False}
    })

    r = as_admin.post('/projects', json={
        'group': group,
        'label': 'test_project_creation',
    })
    assert r.ok
    project_id = r.json()['_id']

    # New projects default to lab being false if group has false
    r = as_admin.get('/projects/' + project_id)
    assert r.ok
    assert r.json()['editions']['lab'] == False

    # Enabling lab is prevented if parent group is not lab edition
    r = as_admin.put('/projects/' + project_id, json={
        'editions': {'lab': True}
    })
    assert r.status_code == 412

    # New projects default to lab being true if group has true and inhert group providers
    compute = str(api_db.providers.find_one({'label': 'Static Compute'})['_id'])
    storage = str(api_db.providers.find_one({'label': 'Primary Storage'})['_id'])
    api_db.groups.update_one({'_id': group}, {
        '$set': {
            'editions': {'lab': True},
            'providers': {'compute': compute, 'storage': storage}
            },
        })
    r = as_admin.post('/projects', json={
        'group': group,
        'label': 'test project lab creation'
    })
    assert r.ok
    project_id = r.json()['_id']
    r = as_admin.get('/projects/' + project_id)
    assert r.ok
    project = r.json()
    assert project['editions']['lab'] == True
    assert project['providers'] == {'compute': compute, 'storage': storage}


    # validate disabling lab edition. Does not remove providers
    r = as_admin.put('/projects/' + project_id, json={
        'editions': {'lab': False}
    })
    assert r.ok
    r = as_admin.get('/projects/' + project_id)
    assert r.ok
    project = r.json()
    assert project['editions']['lab'] == False
    assert project['providers'] == {'compute': compute, 'storage': storage}


    # validate enabling lab edition and providers are the same
    r = as_admin.put('/projects/' + project_id, json={
        'editions': {'lab': True}
    })
    assert r.ok
    r = as_admin.get('/projects/' + project_id)
    assert r.ok
    assert r.json()['editions']['lab'] == True
    project = r.json()
    assert project['editions']['lab'] == True
    assert project['providers'] == {'compute': compute, 'storage': storage}

    # validate enabling lab edition after groups providers have changed, project keeps original providers
    new_compute = bson.ObjectId()
    new_storage = bson.ObjectId()
    api_db.groups.update_one({'_id': group}, {
        '$set': {
            'editions': {'lab': True},
            'providers': {'compute': new_compute, 'storage': new_storage}
            },
        })
    # disable so we can re-enable the 
    r = as_admin.put('/projects/' + project_id, json={
        'editions': {'lab': False}
    })
    assert r.ok
    r = as_admin.put('/projects/' + project_id, json={
        'editions': {'lab': True}
    })
    assert r.ok
    r = as_admin.get('/projects/' + project_id)
    assert r.ok
    project = r.json()
    assert project['editions']['lab'] == True
    assert project['providers'] == {'compute': compute, 'storage': storage}



def test_project_user_permissions(data_builder, as_admin, api_db, as_user, second_storage_provider):

    group = data_builder.create_group()
    r = as_admin.post('/projects', json={
        'group': group,
        'label': 'test_project creation',
        'editions': {'lab': False}
    })
    assert r.ok
    project_id = r.json()['_id']
    # Give user permission on new project
    uid = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project_id + '/permissions', json={'_id': uid, 'access': 'rw'})
    assert r.ok

    r = as_user.put('/projects/' + project_id, json={
        'editions': {'lab': False}
    })
    assert r.status_code == 403
    r = as_user.put('/projects/' + project_id, json={
        'editions': {'lab': True}
    })
    assert r.status_code == 403

    site_storage = str(api_db.singletons.find_one({'_id': 'site'})['providers']['storage'])

    # Add a permission to the group
    user = {'access': 'admin', '_id': uid}
    r = as_admin.post('/groups/' + group + '/permissions', json=user)
    assert r.ok

    # Can not add project with providers one time
    r = as_user.get('/groups/' + group)
    assert r.ok
    group_obj = r.json()
    r = as_user.post('/projects', json={
        'group': group,
        'label': 'new_project_as_user',
        'providers': {
            'storage': site_storage
        },
    })
    assert not r.ok
    assert r.status_code == 403

    # Can add project with providers one time if admin
    r = as_admin.get('/groups/' + group)
    assert r.ok
    group_obj = r.json()
    r = as_admin.post('/projects', json={
        'group': group,
        'label': 'new_project_as_user',
        'providers': {
            'storage': site_storage
        },
    })
    assert r.ok
    project_id = r.json()['_id']
    r = as_admin.get('/projects/' + project_id)
    assert r.ok
    project_obj = r.json()
    assert project_obj['providers']['storage'] == site_storage
    assert project_obj['providers']['compute'] # just needs to be something


    # Can not change providers once set
    r = as_admin.put('/projects/' + project_id, json={
        'providers': {'storage': str(second_storage_provider)},
    })
    assert not r.ok
    assert r.status_code == 422

    # Can not change providers once set as user either
    r = as_user.put('/projects/' + project_id, json={
        'providers': {'storage': str(second_storage_provider)},
    })
    assert not r.ok
    assert r.status_code == 422

