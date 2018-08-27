import bson


def test_subject_collection(data_builder, api_db, as_admin):
    # create simple session w/ subject
    session = data_builder.create_session(subject={'code': 'test', 'age': 123})

    # verify subject is created in separate collection
    session_doc = api_db.sessions.find_one({'_id': bson.ObjectId(session)})
    assert type(session_doc['subject']) is bson.ObjectId
    assert session_doc['subject_age'] == 123
    subject_doc = api_db.subjects.find_one({'_id': session_doc['subject']})
    assert subject_doc['code'] == 'test'
    assert subject_doc['project'] == session_doc['project']
    assert subject_doc['permissions'] == session_doc['permissions']
    assert 'created' in subject_doc
    assert 'modified' in subject_doc
    assert 'age' not in subject_doc

    # verify it's joined by the api
    r = as_admin.get('/sessions/' + session)
    assert r.ok
    assert r.json()['subject']['age'] == 123

    # create new session w/ same subject - implicit subject update
    # NOTE session_2.subject_age will not be populated (even though implicitly known)
    session_2 = data_builder.create_session(subject={'code': 'test', 'sex': 'female'})

    # verify the same subject was used
    session_doc_2 = api_db.sessions.find_one({'_id': bson.ObjectId(session_2)})
    assert session_doc['subject'] == session_doc_2['subject']

    # verify updates were applied
    subject_doc_2 = api_db.subjects.find_one({'_id': session_doc['subject']})
    assert subject_doc_2['sex'] == 'female'


def test_subject_endpoints(data_builder, as_admin, file_form):
    project = data_builder.create_project()

    r = as_admin.get('/subjects')
    assert r.ok
    assert type(r.json()) is list

    r = as_admin.post('/subjects', json={'project': project, 'code': 'test', 'firstname': 'foo', 'sex': 'male'})
    assert r.ok
    subject = r.json()['_id']

    r = as_admin.get('/subjects')
    assert r.ok
    assert subject in [s['_id'] for s in r.json()]
    assert not any('firstname' in s for s in r.json())
    assert not any('sex' in s for s in r.json())

    r = as_admin.get('/subjects/' + subject)
    assert r.ok
    assert r.json()['firstname'] == 'foo'
    assert r.json()['sex'] == 'male'

    r = as_admin.put('/subjects/' + subject, json={'sex': 'female'})
    assert r.ok

    r = as_admin.get('/subjects/' + subject)
    assert r.ok
    assert r.json()['sex'] == 'female'

    r = as_admin.post('/subjects/' + subject + '/files', files=file_form('test.txt'))
    assert r.ok

    r = as_admin.get('/subjects/' + subject)
    assert r.ok
    assert 'test.txt' in [f['name'] for f in r.json()['files']]

    r = as_admin.get('/subjects/' + subject + '/files/test.txt')
    assert r.ok
    assert r.text == 'test\ndata\n'

    r = as_admin.delete('/subjects/' + subject)
    assert r.ok

    r = as_admin.get('/subjects')
    assert subject not in [s['_id'] for s in r.json()]

    r = as_admin.get('/subjects/' + subject)
    assert r.status_code == 404


def test_subject_jobs(api_db, data_builder, as_admin, as_drone, file_form):
    # Create gear, project and subject with one input file
    gear = data_builder.create_gear(gear={'inputs': {'csv': {'base': 'file'}}})
    project = data_builder.create_project()
    r = as_admin.post('/subjects', json={'project': project, 'code': 'test'})
    assert r.ok
    subject = r.json()['_id']
    r = as_admin.post('/subjects/' + subject + '/files', files=file_form('input.csv'))
    assert r.ok

    # Create analysis job on subject
    r = as_admin.post('/subjects/' + subject + '/analyses', json={
        'label': 'online',
        'job': {'gear_id': gear,
                'inputs': {'csv': {'type': 'subject', 'id': subject, 'name': 'input.csv'}}}
    })
    assert r.ok
    analysis = r.json()['_id']

    # Verify analysis was created and is accessible on subject
    r = as_admin.get('/subjects/' + subject + '/analyses')
    assert r.ok
    assert analysis in [a['_id'] for a in r.json()]
    r = as_admin.get('/subjects/' + subject + '/analyses/' + analysis)
    assert r.ok
    assert analysis == r.json()['_id']

    # Verify job was created with it
    r = as_admin.get('/analyses/' + analysis)
    assert r.ok
    job = r.json().get('job')
    assert job

    # Engine upload
    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis, 'job': job},
        files=file_form('output.csv', meta={'type': 'tabular data'}))
    assert r.ok

    # Verify output was uploaded and is accessible on subject/x/analysis/y
    r = as_admin.get('/subjects/' + subject + '/analyses/' + analysis)
    assert r.ok
    assert 'output.csv' in [f['name'] for f in r.json()['files']]
    r = as_admin.get('/subjects/' + subject + '/analyses/' + analysis + '/files/output.csv')
    assert r.ok

    # Create job with subject as destination (and input)
    r = as_admin.post('/jobs/add', json={
        'gear_id': gear,
        'inputs': {'csv': {'type': 'subject', 'id': subject, 'name': 'input.csv'}},
        'destination': {'type': 'subject', 'id': subject}
    })
    assert r.ok
    job = r.json()['_id']
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})

    # Engine upload to subject
    r = as_drone.post('/jobs/' + job + '/prepare-complete', json={'success': True, 'elapsed': 3})
    assert r.ok
    job_ticket = r.json()['ticket']
    r = as_drone.post('/engine',
        params={'level': 'subject', 'id': subject, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={
            'subject': {'files': [{'name': 'result.txt', 'type': 'text'}]}
        })
    )
    assert r.ok

    r = as_admin.get('/subjects/' + subject)
    assert r.ok
    assert 'result.txt' in [f['name'] for f in r.json()['files']]
