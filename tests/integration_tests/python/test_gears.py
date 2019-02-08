import bson

def test_gear_add_versioning(default_payload, randstr, data_builder, as_admin, as_root):
    gear_name = randstr()
    gear_version_1 = '0.0.1'
    gear_version_2 = '0.0.2'
    gear_version_3 = '0.0.1-dev.1'

    gear_payload = default_payload['gear']
    gear_payload['gear']['name'] = gear_name

    # create new gear w/ gear_version_1
    gear_payload['gear']['version'] = gear_version_1
    r = as_admin.post('/gears/' + gear_name, json=gear_payload)
    assert r.ok
    gear_id_1 = r.json()['_id']

    # get gear by id, test name and version
    r = as_admin.get('/gears/' + gear_id_1)
    assert r.ok
    assert r.json()['gear']['name'] == gear_name
    assert r.json()['gear']['version'] == gear_version_1

    # list gears, test gear name occurs only once
    r = as_root.get('/gears', params={'fields': 'all'})
    assert r.ok
    assert sum(gear['gear']['name'] == gear_name for gear in r.json()) == 1

    # list gears with exhaustive flag
    r = as_admin.get('/gears', params={'exhaustive': True, 'fields': 'all'})
    assert r.ok
    assert sum(gear['gear']['name'] == gear_name for gear in r.json()) == 1

    # create new gear w/ gear_version_2
    gear_payload['gear']['version'] = gear_version_2
    r = as_admin.post('/gears/' + gear_name, json=gear_payload)
    assert r.ok
    gear_id_2 = r.json()['_id']

    # get gear by id, test name and version
    r = as_admin.get('/gears/' + gear_id_2)
    assert r.ok
    assert r.json()['gear']['name'] == gear_name
    assert r.json()['gear']['version'] == gear_version_2

    # list gears, test gear name occurs only once
    r = as_admin.get('/gears', params={'fields': 'all'})
    assert r.ok
    assert sum(gear['gear']['name'] == gear_name for gear in r.json()) == 1

    # create new gear w/ gear_version_3
    gear_payload['gear']['version'] = gear_version_3
    gear_payload['gear'].setdefault('custom', {}).setdefault('flywheel', {})['invalid'] = True
    r = as_root.post('/gears/' + gear_name, json=gear_payload)
    assert r.ok
    gear_id_3 = r.json()['_id']

    # list gears with ?all_versions=true, test gear name occurs twice
    r = as_root.get('/gears', params={'fields': 'all', 'all_versions': 'true'})
    assert r.ok
    all_gears = r.json()
    assert sum(gear['gear']['name'] == gear_name for gear in all_gears) == 2
    assert not any(gear['gear']['version'] == gear_version_3 for gear in all_gears)

    # try to create gear w/ same name and version (gear_version_2)
    r = as_admin.post('/gears/' + gear_name, json=gear_payload)
    assert not r.ok

    # delete gears
    r = as_admin.delete('/gears/' + gear_id_1)
    assert r.ok

    r = as_admin.delete('/gears/' + gear_id_2)
    assert r.ok

    r = as_root.delete('/gears/' + gear_id_3)
    assert r.ok

def test_gear_add_with_ticket(default_payload, randstr, data_builder, as_root):
	gear_name = randstr()

	gear_payload = default_payload['gear']
	gear_payload['gear']['name'] = gear_name

	r = as_root.post('/gears/prepare-add', json=gear_payload)
	assert r.ok
	ticket_id = r.json()['ticket']

	r = as_root.get('/gears/ticket/' + ticket_id)
	assert r.ok
	assert r.json() is not None

	r = as_root.get('/gears/my-tickets')
	assert r.ok
	assert len(r.json()) == 1

	r = as_root.get('/gears/my-tickets?gear_names_only=1')
	assert r.ok
	assert len(r.json()) == 1
	assert str(r.json()[0]) == r.json()[0]

def test_gear_add_invalid(default_payload, randstr, as_admin):
    gear_name = 'test-gear-add-invalid-' + randstr()

    # try to add invalid gear - missing name
    r = as_admin.post('/gears/' + gear_name, json={})
    assert r.status_code == 400

    # try to add invalid gear - manifest validation error
    r = as_admin.post('/gears/' + gear_name, json={'gear': {'name': gear_name}})
    assert r.status_code == 400

    # try to add invalid gear - manifest validation error of non-root-level key
    gear_payload = default_payload['gear']
    gear_payload['gear']['inputs'] = {'invalid': 'inputs'}
    r = as_admin.post('/gears/' + gear_name, json=gear_payload)
    assert r.status_code == 400

def test_gear_access(data_builder, as_public, as_admin, as_user):
    gear = data_builder.create_gear()

    # test login required
    r = as_public.get('/gears')
    assert r.status_code == 403

    r = as_public.get('/gears/' + gear)
    assert r.status_code == 403

    r = as_public.get('/gears/' + gear + '/invocation')
    assert r.status_code == 403

    r = as_public.get('/gears/' + gear + '/suggest/projects/test-id')
    assert r.status_code == 403

    # test superuser required with user
    r = as_user.post('/gears/' + gear, json={'test': 'payload'})
    assert r.status_code == 403

    r = as_user.delete('/gears/' + gear)
    assert r.status_code == 403

    # as_admin has root set to True so it's the same as as_root
    # As far as I can tell this is because the update to set root to True in as_root doesn't work
    # # test superuser required
    # r = as_admin.post('/gears/' + gear, json={'test': 'payload'})
    # assert r.status_code == 403
    #
    # r = as_admin.delete('/gears/' + gear)
    # assert r.status_code == 403

def test_gear_invocation_and_suggest(data_builder, file_form, as_admin, as_user):
    gear = data_builder.create_gear()
    group = data_builder.create_group(label='test-group')
    project = data_builder.create_project(label='test-project')
    session = data_builder.create_session(label='test-session', subject={'code': 'test-subject'})
    session2 = data_builder.create_session(label='test-session-2', subject={'code': 'test-subject-2'})
    subject = as_admin.get('/sessions/' + session).json()['subject']['_id']
    subject2 = as_admin.get('/sessions/' + session2).json()['subject']['_id']
    acquisition = data_builder.create_acquisition(label='test-acquisition')
    acquisition2 = data_builder.create_acquisition(label='test-acquisition', session=session2)
    acquisition3 = data_builder.create_acquisition(label='test-acquisition', session=session2)

    user_id = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'rw'})
    assert r.ok

    # Add collection with only the 3rd acquisition
    collection = as_admin.post('/collections', json={'label': 'test-collection'}).json()['_id']
    assert as_admin.put('/collections/' + collection, json={
        'contents': {
            'operation': 'add',
            'nodes': [
                {'level': 'acquisition', '_id': acquisition3}
            ],
        }
    }).ok
    r = as_admin.post('/collections/' + collection + '/permissions', json={'_id': user_id, 'access': 'rw'})


    # Add files to collection/project/sessions/acquisition
    as_user.post('/collections/' + collection + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))
    as_user.post('/projects/' + project + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))
    as_user.post('/sessions/' + session + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))
    as_user.post('/sessions/' + session2 + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))
    as_user.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))
    as_user.post('/acquisitions/' + acquisition2 + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))
    as_user.post('/acquisitions/' + acquisition3 + '/files', files=file_form(
        'one.csv', meta={'name': 'one.csv'}))


    # Add analysis
    analysis = as_user.post('/sessions/' + session + '/analyses', files=file_form(
        'one.csv', meta={'label': 'test', 'outputs': [{'name': 'one.csv'}]})).json()['_id']
    analysis2 = as_user.post('/sessions/' + session2 + '/analyses', files=file_form(
        'one.csv', meta={'label': 'test', 'outputs': [{'name': 'one.csv'}]})).json()['_id']

    # test invocation
    r = as_user.get('/gears/' + gear + '/invocation')
    assert r.ok

    r = as_user.delete('/projects/' + project + '/permissions/' + user_id)
    assert r.ok

    # Try to suggest project without access to project
    r = as_user.get('/gears/' + gear + '/suggest/projects/' + project)
    assert r.status_code == 403

    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'rw'})
    assert r.ok

    # test suggest project
    r = as_user.get('/gears/' + gear + '/suggest/projects/' + project)
    assert r.ok

    assert len(r.json()['children']['subjects']) == 2
    assert len(r.json()['children']['analyses']) == 0
    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 1


    # test suggest subject
    r = as_user.get('/gears/' + gear + '/suggest/subjects/' + subject)
    assert r.ok

    assert len(r.json()['children']['sessions']) == 1
    assert len(r.json()['children']['analyses']) == 0
    assert len(r.json()['files']) == 0
    assert len(r.json()['parents']) == 2


    # test suggest session
    r = as_user.get('/gears/' + gear + '/suggest/sessions/' + session)
    assert r.ok

    assert len(r.json()['children']['acquisitions']) == 1
    assert len(r.json()['children']['analyses']) == 1
    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 3


    # test suggest acquisition
    r = as_user.get('/gears/' + gear + '/suggest/acquisitions/' + acquisition)
    assert r.ok

    assert len(r.json()['children']['analyses']) == 0
    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 4


    # test suggest analysis
    r = as_user.get('/gears/' + gear + '/suggest/analyses/' + analysis)
    assert r.ok

    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 4


    ### Test with collection context

    # test suggest project
    r = as_user.get('/gears/' + gear + '/suggest/collections/' + collection, params={'collection': collection})
    assert r.ok

    assert len(r.json()['children']['subjects']) == 1
    assert len(r.json()['children']['analyses']) == 0
    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 0


    # test suggest subject
    r = as_user.get('/gears/' + gear + '/suggest/subjects/' + subject2, params={'collection': collection})
    assert r.ok

    assert len(r.json()['children']['sessions']) == 1
    assert len(r.json()['children']['analyses']) == 0
    assert len(r.json()['files']) == 0
    assert len(r.json()['parents']) == 1


    # test suggest session
    r = as_user.get('/gears/' + gear + '/suggest/sessions/' + session2, params={'collection': collection})
    assert r.ok

    assert len(r.json()['children']['acquisitions']) == 1
    assert len(r.json()['children']['analyses']) == 1
    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 2


    # test suggest acquisition
    r = as_user.get('/gears/' + gear + '/suggest/acquisitions/' + acquisition3, params={'collection': collection})
    assert r.ok

    assert len(r.json()['children']['analyses']) == 0
    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 3


    # test suggest analysis
    r = as_user.get('/gears/' + gear + '/suggest/analyses/' + analysis2, params={'collection': collection})
    assert r.ok

    assert len(r.json()['files']) == 1
    assert len(r.json()['parents']) == 3


    # clean up
    as_admin.delete('/collections/' + collection)


def test_gear_context(data_builder, default_payload, as_admin, as_user, randstr):
    project_label = randstr()
    project_info = {
        'test_context_value': 3,
        'context': {
            'test_context_value': 'project_context_value'
        }
    }
    project = data_builder.create_project(label=project_label, info=project_info)

    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'rw'}).ok

    session_label = randstr()
    session = data_builder.create_session(project=project, label=session_label)

    acquisition_label = randstr()
    acquisition_info = {
        'context': {
            'test_context_value2': 'acquisition_context_value'
        }
    }
    acquisition = data_builder.create_acquisition(session=session, label=acquisition_label, info=acquisition_info)

    # Add analysis
    analysis = as_admin.post('/sessions/' + session + '/analyses', json={'label': 'test'}).json()['_id']

    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'test_context_value': {
            'base': 'context'
        },
        'test_context_value2': {
            'base': 'context'
        },
        'test_context_value3': {
            'base': 'context'
        },
        'text-file': {
            'base': 'file',
            'type': {'enum': ['text']}
        }
    }

    r = as_admin.post('/gears/' + gear_name, json=gear_doc)
    assert r.ok
    gear = r.json()['_id']

    # Get session level
    r = as_user.get('/gears/' + gear + '/context/sessions/' + session)
    assert r.ok
    result = r.json()

    assert 'text-file' not in result

    assert 'test_context_value' in result
    assert result['test_context_value'] == {
        'found': True,
        'value': 'project_context_value',
        'container_type': 'project',
        'id': project,
        'label': project_label
    }

    assert 'test_context_value2' in result
    assert result['test_context_value2'] == { 'found': False }

    assert 'test_context_value3' in result
    assert result['test_context_value3'] == { 'found': False }

    # Override context at session level
    r = as_admin.post('/sessions/' + session + '/info', json={
        'set': {
            'context': {
                'test_context_value': 'session_context_value',
                'test_context_value3': 'session_context_value3'
            }
        }
    })
    assert r.ok

    # Get analysis level
    r = as_user.get('/gears/' + gear + '/context/analyses/' + analysis)
    assert r.ok

    # Get acquisition level
    r = as_user.get('/gears/' + gear + '/context/acquisitions/' + acquisition)
    assert r.ok
    result = r.json()

    assert result['test_context_value'] == {
        'found': True,
        'value': 'session_context_value',
        'container_type': 'session',
        'id': session,
        'label': session_label
    }

    assert result['test_context_value2'] == {
        'found': True,
        'value': 'acquisition_context_value',
        'container_type': 'acquisition',
        'id': acquisition,
        'label': acquisition_label
    }

    assert result['test_context_value3'] == {
        'found': True,
        'value': 'session_context_value3',
        'container_type': 'session',
        'id': session,
        'label': session_label
    }

    # Get session level
    r = as_user.get('/gears/' + gear + '/context/projects/' + project)
    assert r.ok
    result = r.json()

    assert result['test_context_value'] == {
        'found': True,
        'value': 'project_context_value',
        'container_type': 'project',
        'id': project,
        'label': project_label
    }
    assert result['test_context_value2'] == { 'found': False }
    assert result['test_context_value3'] == { 'found': False }

    # Cleanup
    r = as_admin.delete('/gears/' + gear)
    assert r.ok

def test_filter_gears_read_only_key(randstr, data_builder, default_payload, as_admin):
    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'api_key': {
            'base': 'api-key',
            'read-only': True
        }
    }

    ro_gear = data_builder.create_gear(gear=gear_doc['gear'])

    non_key_gear = data_builder.create_gear()

    gear_doc['gear']['inputs']['api_key']['read-only'] = False
    gear_doc['gear']['name'] = randstr()
    rw_gear = data_builder.create_gear(gear=gear_doc['gear'])



    r = as_admin.get('/gears', params={'filter': 'read_only_key'})
    assert r.ok
    assert len(r.json()) == 2
    for response_gear in r.json():
        assert response_gear['_id'] != rw_gear
