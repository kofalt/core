def test_permissions(data_builder, as_admin):
    project = data_builder.create_project()
    user_1 = data_builder.create_user(_id='test-permissions-1@user.com')
    user_2 = data_builder.create_user(_id='test-permissions-2@user.com')

    permissions_path = '/projects/' + project + '/permissions'
    user_1_path = permissions_path + '/' + user_1
    user_2_path = permissions_path + '/' + user_2

    # GET is not allowed for general permissions path
    r = as_admin.get(permissions_path)
    assert r.status_code == 405

    # Try to add permission for unknown user
    r = as_admin.post(permissions_path, json={
        '_id': 'fake_user@yahoo.com',
        'access': 'admin'
        })
    assert r.status_code == 402

    # Add permissions for user 1
    r = as_admin.post(permissions_path, json={
        '_id': user_1,
        'access': 'ro'
    })
    assert r.ok

    # Verify permissions for user 1
    r = as_admin.get(user_1_path)
    assert r.ok
    perms = r.json()
    assert perms['_id'] == user_1
    assert perms['access'] == 'ro'

    # Update user 1 to have admin access
    r = as_admin.put(user_1_path, json={'access': 'admin'})
    assert r.ok

    # Add user 2 to have ro access
    r = as_admin.post(permissions_path, json={
        '_id': user_2,
        'access': 'ro'
    })
    assert r.ok

    # Attempt to change user 2's id to user 1
    r = as_admin.put(user_2_path, json={'_id': user_1})
    assert r.status_code == 404

    # Delete user 2
    r = as_admin.delete(user_2_path)
    assert r.ok

    # Ensure user 2 is gone
    r = as_admin.get(user_2_path)
    assert r.status_code == 404

def test_group_permissions(data_builder, as_admin, as_public):
    # Test permissions for groups
    api_key = '4hOn5aBx/nUiI0blDbTUPpKQsEbEn74rH9z5KctlXw6GrMKdicPGXKQg'
    user = data_builder.create_user(api_key=api_key)
    group = data_builder.create_group()

    as_other_user = as_public
    as_other_user.headers.update({'Authorization': 'scitran-user ' + api_key})

    permissions_path = '/groups/' + group + '/permissions'
    local_user_permissions_path = permissions_path + '/' + user
    admin_user_permissions_path = permissions_path + '/' + as_admin.get('/users/self').json()['_id']

    # Cannot retrieve permissions that don't exist
    r = as_admin.get(local_user_permissions_path)
    assert r.status_code == 404

    # Create permission for user
    r = as_admin.post(permissions_path, json={'_id': user, 'access': 'rw'})
    assert r.ok

    # Verify new user permission
    r = as_admin.get(local_user_permissions_path)
    assert r.ok
    permission = r.json()
    assert permission['_id'] == user
    assert permission['access'] == 'rw'

    # 'rw' users cannot access other user permissions
    r = as_other_user.get(admin_user_permissions_path)
    assert r.status_code == 403

    # Upgrade user to admin
    r = as_admin.put(local_user_permissions_path, json={'access': 'admin'})
    assert r.ok

    # User should now be able to access other permissions
    r = as_other_user.get(admin_user_permissions_path)
    assert r.ok

    # Change user back to 'rw' access
    r = as_admin.put(local_user_permissions_path, json={'access': 'rw'})
    assert r.ok

    # User is now forbidden again
    r = as_other_user.get(admin_user_permissions_path)
    assert r.status_code == 403

    # Delete permission
    r = as_admin.delete(local_user_permissions_path)
    assert r.ok

    # Verify delete
    r = as_admin.get(local_user_permissions_path)
    assert r.status_code == 404

def test_permission_recursion(data_builder, as_admin):
    """
       Permissions changed on parent containers should propagate
       down to children containers.
    """

    api_key = '4hOn5aBx/nUiI0blDbTUPpKQsEbEn74rH9z5KctlXw6GrMKdiceeeeee'
    user = data_builder.create_user(api_key=api_key)
    group = data_builder.create_group()
    project1 = data_builder.create_project(group=group)
    project2 = data_builder.create_project(group=group)

    subject1 = data_builder.create_subject(code='recurs1', project=project1)
    subject2 = data_builder.create_subject(code='recurs2', project=project2)

    assert as_admin.put('/subjects/' + subject2,
                        json={'project': project2})

    assert as_admin.post('/projects/' + project2 + '/permissions',
                         json={'_id': user, 'access': 'admin'}).ok

    project1_perms = as_admin.get('/projects/' + project1).json()['permissions']
    project2_perms = as_admin.get('/projects/' + project2).json()['permissions']
    subject1_perms = as_admin.get('/subjects/' + subject1).json()['permissions']
    subject2_perms = as_admin.get('/subjects/' + subject2).json()['permissions']

    assert project1_perms != project2_perms
    assert subject1_perms == project1_perms
    assert subject2_perms == project2_perms
