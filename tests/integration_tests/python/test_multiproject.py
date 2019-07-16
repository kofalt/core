import bson
import pytest


@pytest.fixture(scope='function')
def upload_file_form(file_form, merge_dict, randstr):
    def create_form(**meta_override):
        prefix = randstr()
        names = ('project', 'subject', 'session', 'acquisition', 'unused')
        files = {name: '{}-{}.csv'.format(prefix, name) for name in names}
        meta = {
            'project': {
                'label': prefix + '-project-label',
                'files': [{'name': files['project']}],
                'tags': ['one', 'two']
            },
            'session': {
                'uid': prefix + '-session-uid',
                'label': prefix + '-session-label',
                'subject': {
                    'code': prefix + '-subject-code'
                },
                'files': [{'name': files['session']}],
                'tags': ['one', 'two']
            },
            'acquisition': {
                'uid': prefix + '-acquisition-uid',
                'label': prefix + '-acquisition-label',
                'files': [{'name': files['acquisition']}],
                'tags': ['one', 'two']
            }
        }
        if meta_override:
            merge_dict(meta, meta_override)
        return file_form(*files.values(), meta=meta)

    return create_form


def test_adhoc_not_lab(as_admin, data_builder, api_db, file_form, upload_file_form, as_drone, randstr):

    # We need to have some existing containers for ad-hoc testing
    group = data_builder.create_group()
    api_db.groups.update({'_id': group}, {'$set': {'editions.lab': False}})
    r = as_admin.get('/groups/' + group)
    assert r.ok
    assert r.json()['editions']['lab'] == False

    gear = data_builder.create_gear(gear={'inputs': {'csv': {'base': 'file'}}})
    project = data_builder.create_project(label='multi test non lab', editions={'lab': False})

    # This is both a test for making sure device CAN create but also we need it for ad-hoc user creation
    r = as_drone.post('/subjects', json={'project': project, 'code': 'test-no-lab', 'firstname': 'foo', 'sex': 'male'})
    assert r.ok
    subject = r.json()

    r = as_drone.post('/sessions', json={'project': project, 'label': 'test can create', 'subject': subject})
    assert r.ok
    session1 = r.json()


    # With lab off users can not create adhoc subject, session, analyses
    # Tries to create ad hoc project which inherts lab False from group
    r = as_admin.get('/projects/' + project)
    assert r.ok
    assert r.json()['editions']['lab'] == False
    r = as_admin.post('/subjects', json={'project': project, 'code': 'test2--no-lab', 'firstname': 'foo', 'sex': 'male'})
    assert not r.ok
    assert r.status_code == 403

    r = as_admin.post('/sessions', json={'project': project, 'label': 'test not create', 'subject': subject})
    assert not r.ok
    assert r.status_code == 403


    # Can create an ad hoc anquisition.
    adhoc_session = randstr()
    adhoc_project = randstr()
    r = as_drone.post('/upload/reaper', files=upload_file_form(
        group={'_id': group},
        project={'label': adhoc_project},
        session={'uid': adhoc_session},
    ))
    assert r.ok

    # We need to have a session and acquisition to try and make an ad-hoc analyses
    api_db.projects.update({'_id': bson.ObjectId(project)}, {'$set': {'editions.lab': True}})
    acquisition = data_builder.create_acquisition()
    api_db.projects.update({'_id': bson.ObjectId(project)}, {'$set': {'editions.lab': False}})
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'input.txt', meta={'name': 'input.txt', 'type': 'txt'}))
    assert r.ok
    # analysis with inputs is considered ad-hoc
    r = as_admin.post('/projects/' + project + '/analyses', json={
        'label': 'analysis_label',
        'inputs': [
            {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'},
        ]
    })
    assert not r.ok

    api_db.projects.update({'_id': bson.ObjectId(project)}, {'$set': {'editions.lab': True}})
    session2 = data_builder.create_session(project=project)
    api_db.projects.update({'_id': bson.ObjectId(project)}, {'$set': {'editions.lab': False}})
    r = as_admin.post('/sessions/' + session2 + '/analyses', json={
        'label': 'offline',
        'inputs': [{'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}],
        'info': {'bar': 'bar'}
    })
    assert not r.ok

    # Clean up the built data
    r = as_admin.get('/sessions?filter=uid=' + adhoc_session)
    assert r.ok
    assert as_admin.delete('/sessions/' + r.json()[0]['_id']).ok
    assert as_admin.delete('/subjects/' + r.json()[0]['parents']['subject']).ok

    r = as_admin.delete('/subjects/' + subject['_id'])
    assert r.ok


def test_adhoc_lab_edition(as_admin, data_builder, api_db, file_form, upload_file_form, as_drone, randstr):
    '''Now verify it works with lab edition'''

    group = data_builder.create_group()
    project = data_builder.create_project(label='multi test lab enabled')
    api_db.projects.update({'_id': bson.ObjectId(project)}, {'$set': {'editions.lab': True}});
    api_db.groups.update({'_id': group}, {'$set': {'editions.lab': True}});
    r = as_admin.get('/groups/' + group)
    assert r.ok
    assert r.json()['editions']['lab'] == True
    r = as_admin.get('/projects/' + project)
    assert r.ok
    assert r.json()['editions']['lab'] == True 


    # Create ad hoc from group level
    adhoc_session = randstr()
    r = as_drone.post('/upload/reaper', files=upload_file_form(
        group={'_id': group},
        session={'uid': adhoc_session},
    ))
    assert r.ok

    # We need to have a session and acquisition to try and make an ad-hoc analysis
    acquisition = data_builder.create_acquisition()
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'input.txt', meta={'name': 'input.txt', 'type': 'txt'}))
    assert r.ok
    # analysis with inputs is considered ad-hoc
    r = as_admin.post('/projects/' + project + '/analyses', json={
        'label': 'analysis_label',
        'inputs': [
            {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'},
        ]
    })
    assert r.ok

    # analysis with inputs is considered ad-hoc
    r = as_admin.post('/projects/' + project + '/analyses', json={
        'label': 'analysis_label',
        'inputs': [
            {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'},
        ]
    })
    assert r.ok

    session = data_builder.create_session()
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'offline',
        'inputs': [{'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}],
        'info': {'bar': 'bar'}
    })
    assert r.ok


    # NON ad-hoc creation
    r = as_admin.get('/projects/' + project)
    assert r.ok
    assert r.json()['editions']['lab'] == True

    # POST /subjects
    r = as_admin.post('/sessions', json={'project': project, 'label': 'test create'})
    assert r.ok
    session = r.json()
    assert as_admin.delete('/sessions/' + session['_id']).ok

    # POST /subjects
    r = as_admin.post('/subjects', json={'project': project, 'code': 'test', 'firstname': 'foo', 'sex': 'male'})
    assert r.ok
    subject = r.json()
    assert as_admin.delete('/subjects/' + subject['_id']).ok

    # Cleanup up adhoc
    r = as_admin.get('/sessions?filter=uid=' + adhoc_session)
    assert r.ok
    assert as_admin.delete('/sessions/' + r.json()[0]['_id']).ok
    assert as_admin.delete('/subjects/' + r.json()[0]['parents']['subject']).ok
