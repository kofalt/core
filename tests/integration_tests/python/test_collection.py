def test_collections(data_builder, as_admin, as_user, as_public):
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()

    # try to create collection as public
    r = as_public.post('/collections', json={
        'label': 'SciTran/Testing'
    })
    assert r.status_code == 403

    # create and delete collection as user
    r = as_user.post('/collections', json={
        'label': 'SciTran/Testing'
    })
    assert r.ok
    collection = r.json()['_id']

    # Make sure admin can't see without exhaustive or permissions
    r = as_admin.get('/collections')
    assert r.ok
    assert len(r.json()) == 0

    # With exhaustive flag, the collection is returned
    r = as_admin.get('/collections', params={'exhaustive': True})
    assert r.ok
    assert len(r.json()) == 1

    r = as_user.delete('/collections/' + collection)
    assert r.ok

    # create collection
    r = as_admin.post('/collections', json={
        'label': 'SciTran/Testing'
    })
    assert r.ok
    collection = r.json()['_id']

    # get all collections w/ stats=true
    r = as_admin.get('/collections', params={'stats': 'true'})
    assert r.ok
    assert all('session_count' in coll for coll in r.json())

    # get all collections as user, should be none
    r = as_user.get('/collections')
    assert r.ok
    assert len(r.json()) == 0

    # get collection
    r = as_admin.get('/collections/' + collection)
    assert r.ok

    # test empty update
    r = as_admin.put('/collections/' + collection, json={})
    assert r.status_code == 400

    # add session to collection
    r = as_admin.put('/collections/' + collection, json={
        'contents': {
            'operation': 'add',
            'nodes': [
                {'level': 'session', '_id': session}
            ],
        }
    })
    assert r.ok

    # test if collection is listed at acquisition
    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    assert collection in r.json()['collections']


    ###
    #   Test user only sees sessions/acquisitions they have access to
    ###

    project2 = data_builder.create_project()
    session2 = data_builder.create_session(project=project2)
    acquisition2 = data_builder.create_acquisition(session=session2)

    # test user cannot access sessions/acquisitions of collection without perms
    r = as_user.get('/collections/' + collection)
    assert r.status_code == 403
    r = as_user.get('/collections/' + collection + '/sessions')
    assert r.status_code == 403
    r = as_user.get('/collections/' + collection + '/acquisitions')
    assert r.status_code == 403

    # add user to collection
    r = as_user.get('/users/self')
    assert r.ok
    uid = r.json()['_id']

    r = as_admin.post('/collections/' + collection + '/permissions', json={'_id': uid, 'access': 'rw'})
    assert r.ok
    r = as_admin.post('/projects/' + project2 + '/permissions', json={'_id': uid, 'access': 'rw'})
    assert r.ok

    # add session2 to collection
    r = as_user.put('/collections/' + collection, json={
        'contents': {
            'operation': 'add',
            'nodes': [
                {'level': 'session', '_id': session2}
            ],
        }
    })
    assert r.ok

    r = as_admin.put('/collections/' + collection + '/permissions/' + uid, json={'access': 'ro'})
    assert r.ok
    r = as_admin.delete('/projects/' + project2 + '/permissions/' + uid)
    assert r.ok

    # test user cannot see sessions or acquisitions
    r = as_user.get('/collections/' + collection + '/sessions')
    assert r.ok
    assert r.json() == []

    r = as_user.get('/collections/' + collection + '/acquisitions')
    assert r.ok
    assert r.json() == []

    # add user to project
    r = as_admin.post('/projects/' + project2 + '/permissions', json={'_id': uid, 'access': 'ro'})
    assert r.ok

    # test user can now see some of sessions and acquisitions
    r = as_user.get('/collections/' + collection + '/sessions')
    assert r.ok
    sessions = r.json()
    assert len(sessions) == 1
    assert sessions[0]['_id'] == session2

    r = as_user.get('/collections/' + collection + '/acquisitions')
    assert r.ok
    acquisitions = r.json()
    assert len(acquisitions) == 1
    assert acquisitions[0]['_id'] == acquisition2

    r = as_admin.put('/collections/' + collection + '/permissions/' + uid, json={'access': 'admin'})

    # delete collection
    r = as_user.delete('/collections/' + collection)
    assert r.ok

    # try to get deleted collection
    r = as_user.get('/collections/' + collection)
    assert r.status_code == 404

    # test if collection is listed at acquisition
    r = as_user.get('/acquisitions/' + acquisition)
    assert collection not in r.json()['collections']


def test_collection_stats(data_builder, as_admin, as_user, as_public):
    project = data_builder.create_project()
    subject_1 = data_builder.create_subject(project=project, label='subject1')
    subject_2 = data_builder.create_subject(project=project, label='subject2')
    session_1 = data_builder.create_session(subject={'_id': subject_1})
    session_2 = data_builder.create_session(subject={'_id': subject_2})
    acquisition_1 = data_builder.create_acquisition(session=session_1)
    acquisition_2 = data_builder.create_acquisition(session=session_2)

    # === Empty Collection
    # create collection
    r = as_admin.post('/collections', json={
        'label': 'SciTran/TestingStats'
    })
    assert r.ok
    collection = r.json()['_id']

    # get all collections w/ stats=true
    r = as_admin.get('/collections', params={'stats': 'true'})
    assert r.ok
    assert all('session_count' in coll for coll in r.json())

    # Check stats results
    coll_results = {coll['_id']: coll for coll in r.json()}
    assert collection in coll_results
    assert coll_results[collection]['session_count'] == 0
    assert coll_results[collection]['subject_count'] == 0

    # add session to collection
    r = as_admin.put('/collections/' + collection, json={
        'contents': {
            'operation': 'add',
            'nodes': [
                {'level': 'session', '_id': session_1},
                {'level': 'session', '_id': session_2}
            ],
        }
    })
    assert r.ok

    # get all collections w/ stats=true
    r = as_admin.get('/collections', params={'stats': 'true'})
    assert r.ok
    assert all('session_count' in coll for coll in r.json())

    # Check stats results
    coll_results = {coll['_id']: coll for coll in r.json()}
    assert collection in coll_results
    assert coll_results[collection]['session_count'] == 2
    assert coll_results[collection]['subject_count'] == 2

    # === Delete subject_2
    r = as_admin.delete('/subjects/' + subject_2)
    assert r.ok

    r = as_admin.get('/collections', params={'stats': 'true'})
    assert r.ok
    coll_results = {coll['_id']: coll for coll in r.json()}

    assert collection in coll_results
    assert coll_results[collection]['session_count'] == 1
    assert coll_results[collection]['subject_count'] == 1

    # delete collection
    r = as_admin.delete('/collections/' + collection)
    assert r.ok
