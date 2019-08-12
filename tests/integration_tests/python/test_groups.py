import bson
from dateutil.parser import parse

def test_groups(as_user, as_admin, data_builder, api_db):
    # Cannot find a non-existant group
    r = as_admin.get('/groups/non-existent')
    assert r.status_code == 404

    group = data_builder.create_group()
    user_id = data_builder.create_user(_id='test-user@user.com')
    r = as_admin.post('/groups/' + group + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})
    assert r.ok

    # Able to find new group
    r = as_user.get('/groups/' + group)
    assert r.ok
    initial_modified = r.json()['modified']
    created = r.json()['created']
    assert r.json()['revision'] == 1

    # Test that POST group with same id doesn't update created
    r = as_admin.post('/groups', json={'_id': group})
    assert r.ok
    r = as_admin.get('/groups/' + group)
    assert r.ok
    first_modified = r.json()['modified']
    d1 = parse(initial_modified)
    d2 = parse(first_modified)
    assert d2 >= d1

    assert r.json()['created'] == created

    # Test to make sure that list of roles nor name exists in a newly created group
    r = as_admin.get('/groups/' + group)
    assert r.json().get('roles', 'No Roles') == 'No Roles'
    assert r.json().get('name', 'No Name') == 'No Name'

    # Able to change group label
    group_label = 'New group label'
    r = as_user.put('/groups/' + group, json={'label': group_label})
    assert r.ok

    # Get the group again to compare timestamps
    r = as_user.get('/groups/' + group)
    assert r.ok
    second_modified = r.json()['modified']
    d1 = parse(first_modified)
    d2 = parse(second_modified)
    assert d2 > d1
    assert r.json()['revision'] == 2

    # Try adding a tag with a slash
    tag_name = 'Grey/2'
    r = as_user.post('/groups/' + group + '/tags', json={'value': tag_name})
    assert r.status_code == 400

    # Add a tag to the group
    tag_name = 'Grey2'
    r = as_user.post('/groups/' + group + '/tags', json={'value': tag_name})
    assert r.ok

    # Get the group again to compare timestamps for the Add tag test groups
    r = as_user.get('/groups/' + group)
    assert r.ok
    third_modified = r.json()['modified']
    d3 = parse(third_modified)
    assert d3 > d2
    assert r.json()['revision'] == 3

    # Try editting the tag so that it includes a slash
    new_tag_name = 'B/rown'
    r = as_user.put('/groups/' + group + '/tags/' + tag_name, json={'value': new_tag_name})
    assert r.status_code == 400

    # Edit the tag
    new_tag_name = 'Brown'
    r = as_user.put('/groups/' + group + '/tags/' + tag_name, json={'value': new_tag_name})
    assert r.ok

    # Get the group again to compare timestamps for the Edit tag test groups
    r = as_user.get('/groups/' + group)
    assert r.ok
    fourth_modified = r.json()['modified']
    d4 = parse(fourth_modified)
    assert d4 > d3
    assert r.json()['revision'] == 4

    # Delete the tag
    r = as_user.delete('/groups/' + group + '/tags/' + new_tag_name)
    assert r.ok

    # Get the group again to compare timestamps for the Delete tag test groups
    r = as_user.get('/groups/' + group)
    assert r.ok
    fith_modified = r.json()['modified']
    d5 = parse(fith_modified)
    assert d5 > d4
    assert r.json()['revision'] == 5

    # Add a permission to the group
    user = {'access': 'rw', '_id': user_id}
    r = as_user.post('/groups/' + group + '/permissions', json=user)
    assert r.ok

    # Get the group again to compare timestamps for the Add permission test groups
    r = as_user.get('/groups/' + group)
    assert r.ok
    six_modified = r.json()['modified']
    d6 = parse(six_modified)
    assert d6 > d5
    assert r.json()['revision'] == 6

    # Edit a permission in the group
    user = {'access': 'ro', '_id': user_id}
    r = as_user.put('/groups/' + group + '/permissions/' + user['_id'], json=user)
    assert r.ok

    # Get all permissions for each group
    r = as_admin.get('/users/admin@user.com/groups')
    assert r.ok
    assert r.json()[0].get("permissions")[0].get("_id") == "admin@user.com"

    # Get the group again to compare timestamps for the Edit permission test groups
    r = as_user.get('/groups/' + group)
    assert r.ok
    seven_modified = r.json()['modified']
    d7 = parse(seven_modified)
    assert d7 > d6
    assert r.json()['revision'] == 7

    # Delete a permission in the group
    r = as_user.delete('/groups/' + group + '/permissions/' + user['_id'])
    assert r.ok

    # Get the group again to compare timestamps for the Edit permission test groups
    r = as_user.get('/groups/' + group)
    assert r.ok
    eight_modified = r.json()['modified']
    d8 = parse(eight_modified)
    assert d8 > d7
    assert r.json()['revision'] == 8

    group2 = data_builder.create_group()
    r = as_admin.post('/groups/' + group2 + '/permissions', json={'access':'admin','_id':'user@user.com'})
    assert r.ok

    # Test User can get group2
    r = as_user.get('/groups/' + group2)
    assert r.ok

    # Test that group2 shows up in group list for user
    r = as_user.get('/groups')
    assert r.ok
    assert len(r.json()) == 2

    assert r.json()[0].get('permissions', []) != []
    r = as_admin.get('/groups')
    assert r.ok
    assert len(r.json()) > 1

    # Empty put request should 400
    r = as_admin.put('/groups/' + group, json={})
    assert r.status_code == 400

    r = as_admin.get('/groups/' + group)
    assert r.ok
    assert r.json()['label'] == group_label

    # Test join=projects
    project = data_builder.create_project(group=group2)
    r = as_admin.get('/groups', params={'join': 'projects'})
    assert r.ok
    for group in r.json():
        if group["_id"] == group2:
            assert group.get("projects")[0].get("_id") == project

def test_groups_blacklist(as_admin):
    r = as_admin.post('/groups', json={'_id': 'unknown', 'label': 'Unknown group'})
    assert r.status_code == 400

    r = as_admin.post('/groups', json={'_id': 'site', 'label': 'Site group'})
    assert r.status_code == 400

def test_groups_upsert(as_admin, data_builder):
    group_id = data_builder.create_group(label='Original Label')

    r = as_admin.get('/groups/' + group_id)
    assert r.ok
    original_group = r.json()

    r = as_admin.post('/groups', json={'_id': group_id, 'label': 'Fubar'})
    assert r.status_code == 202
    assert r.json() == {'_id': group_id}

    r = as_admin.get('/groups/' + group_id)
    assert r.ok
    updated_group = r.json()

    assert original_group['label'] == updated_group['label']
    assert original_group['created'] == updated_group['created']
    assert original_group['modified'] == updated_group['modified']

def test_groups_editions(as_admin):
    # Test adding empty editions
    group_id = str(bson.ObjectId())
    r = as_admin.post('/groups', json={'_id': group_id, 'label': 'empty_editions'})
    assert r.ok
    r = as_admin.get('/groups/' + group_id)
    group = r.json()
    # By default lab edition is False
    assert group['editions']['lab'] == False

def test_groups_editions_feature(as_admin, data_builder, as_user, with_site_settings, api_db):
    group = data_builder.create_group()

    r = as_user.put('/groups/'+ group, json={'editions': {'lab': True}})
    assert r.status_code == 403

    # Default group has no providers, and we cant change them, as tested in other test cases
    r = as_admin.put('/groups/'+ group, json={'editions': {'lab': True}})
    assert r.status_code == 422

    provider = api_db.providers.find_one({'label': 'Static Compute'})
    provider = str(provider['_id'])

    api_db.groups.update_one({'_id': group}, {'$unset': {'providers' : 1}})
    r = as_admin.put('/groups/'+ group, json={
        'editions': {
            'lab': True
            },
        'providers': {
            'compute': provider
            }
        })
    assert r.status_code == 422

    r = as_admin.put('/groups/'+ group, json={
        'editions': {
            'lab': True
            },
        'providers': {
            'storage': 'deadbeefdeadbeefdeadbeef'
            }
        })
    assert r.status_code == 422

    # Can enable with valid providers
    r = as_admin.put('/groups/'+ group, json={
        'editions': {
            'lab': True
            },
        'providers': {
            'compute': provider,
            'storage': 'deadbeefdeadbeefdeadbeef'
            }
        })
    assert r.status_code == 200

    r = as_admin.put('/groups/'+ group, json={
        'editions': {
            'lab': False
            },
        })
    assert r.status_code == 200
    assert as_admin.get('/groups/' + group).json()['editions']['lab'] == False

    # Can be enabled if providers are already set
    r = as_admin.put('/groups/'+ group, json={
        'editions': {
            'lab': True
            }
        })
    assert r.status_code == 200
    assert as_admin.get('/groups/' + group).json()['editions']['lab'] == True


    # Now add a couple projects with lab true can verify they are disabled on group disable
    r = as_admin.post('/projects', json={'label': 'test-lab-1', 'group': group, 'editions': {'lab': True}})
    assert r.ok
    project1 = r.json()['_id']

    r = as_admin.post('/projects', json={'label': 'test-lab-2', 'group': group, 'editions': {'lab': True}})
    assert r.ok
    project2 = r.json()['_id']

    assert as_admin.get('/projects/' + project1).json()['editions']['lab'] == True
    assert as_admin.get('/projects/' + project2).json()['editions']['lab'] == True
    r = as_admin.get('/projects/' + project1)
    r = as_admin.put('/groups/'+ group, json={
        'editions': {
            'lab': False
            }
        })
    assert r.status_code == 200
    assert as_admin.get('/groups/' + group).json()['editions']['lab'] == False
    assert as_admin.get('/projects/' + project1).json()['editions']['lab'] == False
    assert as_admin.get('/projects/' + project2).json()['editions']['lab'] == False


    # Cleanup
    assert as_admin.delete('/projects/' + project1).ok
    assert as_admin.delete('/projects/' + project2).ok


def test_group_project_access(as_admin, as_user, data_builder):
    group_id = data_builder.create_group()
    project_id = data_builder.create_project(group=group_id)

    # Test user without permissions to project can't access group
    r = as_user.get('/groups/' + group_id)
    assert r.status_code == 403

    # Add user to project permissions but not group
    user_id = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project_id + '/permissions',
                      json={'_id': user_id, 'access': 'ro'})
    assert r.ok

    # Test that user can access group directly
    r = as_user.get('/groups/' + group_id)
    assert r.ok
    assert group_id == r.json()['_id']

    # Test that user cannot write to group
    r = as_user.put('/groups/' + group_id, json={'label': 'NewGroup'})
    assert r.status_code == 403

