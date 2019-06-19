def test_users(data_builder, as_admin, as_user, as_public):
    # List users
    r = as_user.get('/users')
    assert r.ok

    # Try to get self w/o logging in
    r = as_public.get('/users/self')
    assert r.status_code == 400

    # Get self as user
    r = as_user.get('/users/self')
    assert r.ok
    user_id = r.json()['_id']

    # Get self as admin
    r = as_admin.get('/users/self')
    assert r.ok
    admin_id = r.json()['_id']
    assert admin_id != user_id

    # Try to get self's avatar
    r = as_user.get('/users/self/avatar')
    assert r.status_code == 404

    # Get user as user
    r = as_user.get('/users/' + user_id)
    assert r.ok

    # Try to get user avatar as user
    r = as_user.get('/users/' + user_id + '/avatar')
    assert r.status_code == 404

    # Try adding new user missing required attr
    r = as_admin.post('/users', json={
        '_id': 'jane.doe@gmail.com',
        'lastname': 'Doe',
        'email': 'jane.doe@gmail.com',
    })
    assert r.status_code == 400
    assert "'firstname' is a required property" in r.text

    # Add new user
    new_user_id = 'new@user.com'
    r = as_admin.post('/users', json={
        '_id': new_user_id,
        'firstname': 'New',
        'lastname': 'User',
    })
    assert r.ok
    r = as_admin.get('/users/' + new_user_id)
    assert r.ok

    # Add new user as admin
    new_user_id_admin = 'new2@user.com'
    r = as_admin.post('/users', json={
        '_id': new_user_id_admin,
        'firstname': 'New2',
        'lastname': 'User2',
    })
    assert r.ok
    r = as_admin.get('/users/' + new_user_id)
    assert r.ok

    #Get another user as user
    r = as_user.get('/users/' + new_user_id)
    assert r.ok

    # Try getting another user's projects without admin priveledges
    r = as_user.get('/users/' + new_user_id + '/projects')
    assert r.status_code == 403

    # Get another user's projects
    r = as_admin.get('/users/' + new_user_id + '/projects')
    assert r.ok

    # Try to update non-existent user
    r = as_admin.put('/users/nonexistent@user.com', json={'firstname': 'Realname'})
    assert r.status_code == 404

    # Try empty update
    r = as_admin.put('/users/' + new_user_id, json={})
    assert r.status_code == 400

    # Update existing user
    r = as_admin.put('/users/' + new_user_id, json={'firstname': 'Realname'})
    assert r.ok
    assert r.json()['modified'] == 1

    # Update existing user as admin
    r = as_admin.put('/users/' + new_user_id_admin, json={'firstname': 'Realname2'})
    assert r.ok
    assert r.json()['modified'] == 1

    # Disable user, test clear permissions
    project = data_builder.create_project()
    r = as_admin.post('/projects/' + project + '/permissions', json={
        '_id': new_user_id_admin,
        'access': 'ro'
    })
    assert r.ok

    r = as_admin.put('/users/' + new_user_id_admin, json={'disabled': True}, params={'clear_permissions': 1})
    assert r.ok
    assert r.json()['modified'] == 1

    permissions = as_admin.get('/projects/' + project).json().get('permissions', [])
    for p in permissions:
        assert p['_id'] != new_user_id_admin

    # Try to delete non-existent user
    r = as_admin.delete('/users/nonexistent@user.com')
    assert r.status_code == 404

    # Delete user
    r = as_admin.delete('/users/' + new_user_id)
    assert r.ok

    # Delete user
    r = as_admin.delete('/users/' + new_user_id_admin)
    assert r.ok

    # Test HTTPS enforcement on avatar urls
    new_user_id = 'new@user.com'
    r = as_admin.post('/users', json={
        '_id': new_user_id,
        'firstname': 'New',
        'lastname': 'User',
    })
    assert r.ok
    r = as_admin.get('/users/' + new_user_id)
    assert r.ok

    r = as_admin.put('/users/' + new_user_id, json={'avatar': 'https://lh3.googleusercontent.com/-XdUIqdMkCWA/AAAAAAAAAAI/AAAAAAAAAAA/4252rscbv5M/photo.jpg'})
    r = as_admin.get('/users/' + new_user_id)
    assert r.json()['avatar'] == 'https://lh3.googleusercontent.com/-XdUIqdMkCWA/AAAAAAAAAAI/AAAAAAAAAAA/4252rscbv5M/photo.jpg'

    r = as_admin.put('/users/' + new_user_id, json={'avatar': 'http://media.nomadicmatt.com/maldivestop001.jpg', 'avatars': {'custom': 'http://media.nomadicmatt.com/maldivestop001.jpg', 'provider': 'https://lh3.googleusercontent.com/-XdUIqdMkCWA/AAAAAAAAAAI/AAAAAAAAAAA/4252rscbv5M/photo.jpg'}})
    assert r.status_code == 400
    r = as_admin.get('/users/' + new_user_id)
    assert r.json()['avatar'] != 'http://media.nomadicmatt.com/maldivestop001.jpg'

    r = as_admin.delete('/users/' + new_user_id)
    assert r.ok

def test_generate_api_key(data_builder, as_public):
    # Try to generate new api key w/o logging in
    r = as_public.post('/users/self/key')
    assert r.status_code == 400

    new_user = data_builder.create_user(api_key='test')
    as_new_user = as_public
    as_new_user.headers.update({'Authorization': 'scitran-user test'})

    # Generate new api key for user
    r = as_new_user.post('/users/self/key')
    assert r.ok
    assert 'key' in r.json()


def test_reset_wechat_registration(data_builder, as_admin):
    new_user = data_builder.create_user()

    # Reset (create) wechat registration code for user
    r = as_admin.post('/users/' + new_user + '/reset-registration')
    assert r.ok
    assert 'registration_code' in r.json()


def test_bootstrap_not_allowed_twice(bootstrap_users, as_public):
    # Verify that public user creation is only allowed once (used in bootstrap_users)
    r = as_public.post('/users', json={'_id': 'h@cker.man', 'firstname': 'Hax0r', 'lastname': 'Wannabe'})
    assert r.status_code == 403


def test_user_jobs(as_admin, as_user, data_builder, default_payload, file_form):
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    gear_2 = data_builder.create_gear(gear=gear_doc)
    group = data_builder.create_group()
    project = data_builder.create_project(group=group)
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    job_data = {
        'gear_id': gear,
        'inputs': {
            'dicom': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.zip'
            }
        },
        'config': {'two-digit multiple of ten': 20},
        'destination': {
            'type': 'acquisition',
            'id': acquisition
        },
        'tags': ['test-tag']
    }

    # create a job with admin user
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id_1 = r.json()['_id']

    # jobs handler lists that job
    r = as_admin.get('/jobs')
    assert r.ok
    assert job_id_1 in map(lambda job: job['_id'], r.json())

    # user jobs handler doesn't list admin's job
    r = as_user.get('/users/self/jobs')
    assert r.ok
    assert job_id_1 not in map(lambda job: job['_id'], r.json()['jobs'])

    r = as_user.get('/users/self')
    assert r.ok
    uid = r.json()['_id']

    # set as_user perms to rw
    r = as_admin.post('/projects/' + project + '/permissions', json={
        '_id': uid,
        'access': 'rw'
    })
    assert r.ok

    # create job with user
    r = as_user.post('/jobs/add', json=job_data)
    assert r.ok
    job_id_2 = r.json()['_id']

    # user jobs handler lists user's job
    r = as_user.get('/users/self/jobs')
    assert r.ok
    assert job_id_2 in map(lambda job: job['_id'], r.json()['jobs'])

    job_data['gear_id'] = gear_2
    # create another job with user
    r = as_user.post('/jobs/add', json=job_data)
    assert r.ok
    job_id_3 = r.json()['_id']

    r = as_user.get('/gears/' + gear)
    assert r.ok
    gear_name_1 = r.json()['gear']['name']

    # can filter by gear name
    r = as_user.get('/users/self/jobs?gear=' + gear_name_1)
    assert r.ok
    assert len(r.json()['jobs']) == 1
    assert job_id_2 in map(lambda job: job['_id'], r.json()['jobs'])

    r = as_user.get('/gears/' + gear_2)
    assert r.ok
    gear_name_2 = r.json()['gear']['name']

    r = as_user.get('/users/self/jobs?gear=' + gear_name_2)
    assert r.ok
    assert len(r.json()['jobs']) == 1
    assert job_id_3 in map(lambda job: job['_id'], r.json()['jobs'])


def test_user_info(as_user, as_admin):
    user_info = {
        'a': 'b',
        'test': 123,
        'map': {
            'a': 'b'
        },
        'list': [1, 2, 3]
    }

    r = as_user.post('/users/self/info', json={
        'replace': user_info
    })
    assert r.ok

    r = as_admin.post('/users/self/info', json={
        'replace': user_info
    })
    assert r.ok

    r = as_user.get('/users/self/info')
    assert r.ok
    assert r.json() == user_info

    # get only a specific info field
    r = as_user.get('/users/self/info?fields=a')
    assert r.ok
    assert r.json() == {'a': 'b'}

    # can specify multiple fields
    r = as_user.get('/users/self/info?fields=a,map')
    assert r.ok
    assert r.json() == {
        'a': 'b',
        'map': {
            'a': 'b'
        }
    }

    # info field is not returned when listing users
    r = as_user.get('/users')
    assert reduce(lambda x, y: x and y, map(lambda user: 'info' in user, r.json()))

    # Get self as user
    r = as_user.get('/users/self')
    assert r.ok
    user_id = r.json()['_id']

    # Get self as admin
    r = as_admin.get('/users/self')
    assert r.ok
    admin_id = r.json()['_id']

    # user can't get other user's info
    r = as_user.get('/users/' + admin_id)
    assert 'info' not in r.json()

    # user can see its own info
    r = as_user.get('/users/' + user_id)
    assert 'info' in r.json()

    # admin user can see other user's info
    r = as_admin.get('/users/' + user_id)
    assert 'info' in r.json()

def test_users_password_hash(data_builder, as_admin, as_user, as_public, api_db):
    test_user = data_builder.create_user()

    api_db.users.update_one({'_id': test_user}, {'$set': {'password_hash': 'invalid'}})

    # List users
    r = as_user.get('/users')
    assert r.ok
    assert not any(['password_hash' in entry for entry in r.json()])

    # Get user as user
    r = as_user.get('/users/' + test_user)
    assert r.ok
    assert 'password_hash' not in r.json()

    r = as_admin.get('/users/' + test_user)
    assert r.ok
    assert 'password_hash' not in r.json()
