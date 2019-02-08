import bson
import time

def test_batch(data_builder, as_user, as_admin, as_root, as_drone):
    gear = data_builder.create_gear()
    analysis_gear = data_builder.create_gear(category='analysis')
    invalid_gear = data_builder.create_gear(gear={'custom': {'flywheel': {'invalid': True}}})

    empty_project = data_builder.create_project()
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    as_admin.post('/acquisitions/' + acquisition + '/files', files={
        'file': ('test.txt', 'test\ncontent\n')})

    # get all
    r = as_user.get('/batch')
    assert r.ok

    # get all w/o enforcing permissions
    r = as_admin.get('/batch')
    assert r.ok

    # get all as root
    r = as_root.get('/batch')
    assert r.ok

    # get all as admin with exhaustive flag
    r = as_admin.get('/batch', params={'exhaustive':True})
    assert r.ok

    # try to create batch without gear_id/targets
    r = as_admin.post('/batch', json={})
    assert r.status_code == 400

    # try to create batch with different target container types
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [
            {'type': 'session', 'id': 'test-session-id'},
            {'type': 'acquisition', 'id': 'test-acquisition-id'},
        ],
    })
    assert r.status_code == 400

    # try to create batch using an invalid gear
    r = as_admin.post('/batch', json={
        'gear_id': invalid_gear,
        'targets': [{'type': 'session', 'id': 'test-session-id'}],
    })
    assert r.status_code == 400

    # try to create batch for project w/o acquisitions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'project', 'id': empty_project}]
    })
    assert r.status_code == 404

    # try to create batch w/o write permission
    r = as_user.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'project', 'id': project}]
    })
    assert r.status_code == 403

    # create a batch w/ session target
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'session', 'id': session}]
    })
    assert r.ok

    # create a batch w/ acquisition target and target_context
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'acquisition', 'id': acquisition}],
        'target_context': {'type': 'session', 'id': session}
    })
    assert r.ok
    batch_id = r.json()['_id']

    # create a batch w/ analysis gear
    r = as_admin.post('/batch', json={
        'gear_id': analysis_gear,
        'targets': [{'type': 'session', 'id': session}]
    })
    assert r.ok
    analysis_batch_id = r.json()['_id']

    # try to create a batch with invalid preconstructed jobs
    r = as_admin.post('/batch/jobs', json={
        'jobs': [
            {
                'gear_id': gear,
                'inputs': {
                    'dicom': {
                        'type': 'acquisition',
                        'id': acquisition,
                        'name': 'test.zip'
                    }
                },
                'config': { 'two-digit multiple of ten': 20 },
                'destination': {
                    'type': 'acquisition',
                    'id': acquisition
                },
                'tags': [ 'test-tag' ]
            }
        ]
    })
    assert r.status_code == 400
    assert "Job 0" in r.json().get('message')

    # create a batch with preconstructed jobs
    r = as_admin.post('/batch/jobs', json={
        'jobs': [
            {
                'gear_id': gear,
                'config': { 'two-digit multiple of ten': 20 },
                'destination': {
                    'type': 'acquisition',
                    'id': acquisition
                },
                'tags': [ 'test-tag' ]
            }
        ]
    })
    assert r.ok
    job_batch_id = r.json()['_id']

    # try to get non-existent batch
    r = as_admin.get('/batch/000000000000000000000000')
    assert r.status_code == 404

    # try to get batch w/o perms (different user)
    r = as_user.get('/batch/' + batch_id)
    assert r.status_code == 403

    # get batch
    r = as_admin.get('/batch/' + batch_id)
    assert r.ok
    assert r.json()['state'] == 'pending'

    # get batch from jobs
    r = as_admin.get('/batch/' + job_batch_id)
    assert r.ok
    assert r.json()['state'] == 'pending'

    # get batch w/ ?jobs=true
    r = as_admin.get('/batch/' + batch_id, params={'jobs': 'true'})
    assert r.ok
    assert 'jobs' in r.json()

    # get job batch w/ ?jobs=true
    r = as_admin.get('/batch/' + job_batch_id, params={'jobs': 'true'})
    assert r.ok
    assert 'jobs' in r.json()

    # try to cancel non-running batch
    r = as_admin.post('/batch/' + batch_id + '/cancel')
    assert r.status_code == 400

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'

    # try to run non-pending batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.status_code == 400

    # cancel batch
    r = as_admin.post('/batch/' + batch_id + '/cancel')
    assert r.ok

    # test batch.state after calling cancel
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'cancelled'

    # run analysis batch
    r = as_admin.post('/batch/' + analysis_batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + analysis_batch_id)
    assert r.json()['state'] == 'running'

    # run job batch
    r = as_admin.post('/batch/' + job_batch_id + '/run')
    print r.json()
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + job_batch_id)
    assert r.json()['state'] == 'running'

    # Test batch complete
    # create a batch w/ acquisition target and target_context
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'acquisition', 'id': acquisition}],
        'target_context': {'type': 'session', 'id': session}
    })
    assert r.ok
    batch_id = r.json()['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'

    for job in r.json()['jobs']:
        # set jobs to complete
        r = as_drone.put('/jobs/' + job, json={'state': 'running'})
        assert r.ok
        r = as_drone.put('/jobs/' + job, json={'state': 'complete'})
        assert r.ok

    # test batch is complete
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'complete'

    # Test batch failed with acquisition target
    # create a batch w/ acquisition target and target_context
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'acquisition', 'id': acquisition}],
        'target_context': {'type': 'session', 'id': session}
    })
    assert r.ok
    batch_id = r.json()['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'

    for job in r.json()['jobs']:
        # set jobs to failed
        r = as_drone.put('/jobs/' + job, json={'state': 'running'})
        assert r.ok
        r = as_drone.put('/jobs/' + job, json={'state': 'failed'})
        assert r.ok

    # test batch is complete
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'failed'

    # Test batch complete with analysis target
    # create a batch w/ analysis gear
    r = as_admin.post('/batch', json={
        'gear_id': analysis_gear,
        'targets': [{'type': 'session', 'id': session}]
    })
    assert r.ok
    batch_id = r.json()['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'

    for job in r.json()['jobs']:
        # set jobs to complete
        r = as_drone.put('/jobs/' + job, json={'state': 'running'})
        assert r.ok
        r = as_drone.put('/jobs/' + job, json={'state': 'complete'})
        assert r.ok

    # test batch is complete
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'complete'

    # Test batch failed with analysis target
    # create a batch w/ analysis gear
    r = as_admin.post('/batch', json={
        'gear_id': analysis_gear,
        'targets': [{'type': 'session', 'id': session}]
    })
    assert r.ok
    batch_id = r.json()['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'

    for job in r.json()['jobs']:
        # set jobs to failed
        r = as_drone.put('/jobs/' + job, json={'state': 'running'})
        assert r.ok
        r = as_admin.put('/jobs/' + job, json={'state': 'failed'})
        assert r.ok

    # test batch is complete
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'failed'

def test_no_input_batch(data_builder, default_payload, randstr, as_admin, as_drone, api_db):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    session2 = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)

    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'api_key': {
            'base': 'api-key'
        }
    }


    r = as_admin.post('/gears/' + gear_name, json=gear_doc)
    assert r.ok

    gear = r.json()['_id']


    # create a batch w/o inputs targeting sessions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch1 = r.json()

    assert len(batch1['matched']) == 2
    matched_ids = [ x['id'] for x in batch1['matched'] ]
    assert session in matched_ids
    assert session2 in matched_ids

    # create a batch w/o inputs targeting acquisitions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'acquisition', 'id': acquisition}, {'type': 'acquisition', 'id': acquisition2}]
    })
    assert r.ok
    batch2 = r.json()
    assert len(batch2['matched']) == 2
    matched_ids = [ x['id'] for x in batch2['matched'] ]
    assert session in matched_ids
    assert session2 in matched_ids

    # create a batch w/o inputs targeting project
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'project', 'id': project}]
    })
    assert r.ok
    batch3 = r.json()
    assert len(batch3['matched']) == 2
    matched_ids = [ x['id'] for x in batch3['matched'] ]
    assert session in matched_ids
    assert session2 in matched_ids

    batch_id = batch1['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'
    jobs = r.json()['jobs']

    for job in jobs:
        # set jobs to failed
        r = as_drone.put('/jobs/' + job, json={'state': 'running'})
        assert r.ok
        r = as_drone.put('/jobs/' + job, json={'state': 'complete'})
        assert r.ok

    # test batch is complete
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'complete'

    ## Test no-input anlaysis gear ##

    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['category'] = 'analysis'
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'api_key': {
            'base': 'api-key'
        }
    }

    r = as_admin.post('/gears/' + gear_name, json=gear_doc)
    assert r.ok

    gear2 = r.json()['_id']

    # create a batch w/o inputs targeting session
    r = as_admin.post('/batch', json={
        'gear_id': gear2,
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch4 = r.json()

    assert len(batch4['matched']) == 2
    matched_ids = [ x['id'] for x in batch4['matched'] ]
    assert session in matched_ids
    assert session2 in matched_ids
    batch_id = batch4['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'
    jobs = r.json()['jobs']

    for job in jobs:
        # set jobs to failed
        r = as_drone.put('/jobs/' + job, json={'state': 'running'})
        assert r.ok
        r = as_drone.put('/jobs/' + job, json={'state': 'complete'})
        assert r.ok

    # cleanup

    r = as_admin.delete('/gears/' + gear)
    assert r.ok

    r = as_admin.delete('/gears/' + gear2)
    assert r.ok

    # must remove jobs manually because gears were added manually
    api_db.jobs.remove({'gear_id': {'$in': [gear, gear2]}})

def test_no_input_context_batch(data_builder, default_payload, as_admin, file_form, randstr, api_db):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    session2 = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)

    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'test_context_value': {
            'base': 'context'
        }
    }

    r = as_admin.post('/gears/' + gear_name, json=gear_doc)
    assert r.ok
    gear = r.json()['_id']

    # create a batch w/o inputs targeting sessions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch1 = r.json()

    assert len(batch1['matched']) == 2
    assert batch1['matched'][0]['id'] == session
    assert batch1['matched'][1]['id'] == session2

    batch_id = batch1['_id']

    # run batch with no context values
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job configs for inputs
    jobs = r.json()
    job1_inputs = jobs[0]['config']['inputs']
    assert 'test_context_value' in job1_inputs
    assert job1_inputs['test_context_value']['found'] == False

    job2_inputs = jobs[1]['config']['inputs']
    assert 'test_context_value' in job2_inputs
    assert job2_inputs['test_context_value']['found'] == False

    # Set context at project level
    r = as_admin.post('/projects/' + project + '/info', json={
        'set': {
            'test_context_value': 3,
            'context': {
                'test_context_value': 'project_context_value'
            }
        }
    })
    assert r.ok

    # Override context at session level
    r = as_admin.post('/sessions/' + session + '/info', json={
        'set': {
            'context': {
                'test_context_value': 'session_context_value'
            }
        }
    })
    assert r.ok

    # create a batch w/o inputs targeting sessions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch_id = r.json()['_id']

    # run batch with no context values
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job configs for inputs
    jobs = r.json()
    assert jobs[0]['config']['destination']['id'] == session
    job1_inputs = jobs[0]['config']['inputs']
    assert 'test_context_value' in job1_inputs
    assert job1_inputs['test_context_value']['found'] == True
    assert job1_inputs['test_context_value']['value'] == 'session_context_value'

    job2_inputs = jobs[1]['config']['inputs']
    assert jobs[1]['config']['destination']['id'] == session2
    assert 'test_context_value' in job2_inputs
    assert job2_inputs['test_context_value']['found'] == True
    assert job2_inputs['test_context_value']['value'] == 'project_context_value'

    # Cleanup
    r = as_admin.delete('/gears/' + gear)
    assert r.ok

    # must remove jobs manually because gears were added manually
    api_db.jobs.remove({'gear_id': {'$in': [gear]}})

def test_file_input_context_batch(data_builder, default_payload, as_admin, file_form, randstr, api_db):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    session2 = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)

    as_admin.post('/acquisitions/' + acquisition + '/files', files={
        'file': ('test.txt', 'test\ncontent\n')})

    as_admin.post('/acquisitions/' + acquisition2 + '/files', files={
        'file': ('test2.txt', 'test\ncontent2\n')})

    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'test_context_value': {
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

    # create a batch w/o inputs targeting sessions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch1 = r.json()

    assert len(batch1['matched']) == 2
    assert batch1['matched'][0]['_id'] == acquisition
    assert 'inputs' not in batch1['matched'][0]
    assert batch1['matched'][1]['_id'] == acquisition2
    assert 'inputs' not in batch1['matched'][1]

    batch_id = batch1['_id']

    # run batch with no context values
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job configs for inputs
    jobs = r.json()
    job1_inputs = jobs[0]['config']['inputs']
    assert 'test_context_value' in job1_inputs
    assert job1_inputs['test_context_value']['found'] == False

    job2_inputs = jobs[1]['config']['inputs']
    assert 'test_context_value' in job2_inputs
    assert job2_inputs['test_context_value']['found'] == False

    # try to cancel non-running batch
    r = as_admin.post('/batch/' + batch_id + '/cancel')
    assert r.ok

    # Set context at project level
    r = as_admin.post('/projects/' + project + '/info', json={
        'set': {
            'test_context_value': 3,
            'context': {
                'test_context_value': 'project_context_value'
            }
        }
    })
    assert r.ok

    # Override context at session level
    r = as_admin.post('/sessions/' + session + '/info', json={
        'set': {
            'context': {
                'test_context_value': 'session_context_value'
            }
        }
    })
    assert r.ok

    # create a batch w/o inputs targeting sessions
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'acquisition', 'id': acquisition}, {'type': 'acquisition', 'id': acquisition2}]
    })
    assert r.ok
    batch_id = r.json()['_id']

    # run batch with no context values
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job configs for inputs
    jobs = r.json()

    assert jobs[0]['config']['destination']['id'] == acquisition
    job1_inputs = jobs[0]['config']['inputs']
    assert 'test_context_value' in job1_inputs
    assert job1_inputs['test_context_value']['found'] == True
    assert job1_inputs['test_context_value']['value'] == 'session_context_value'

    job2_inputs = jobs[1]['config']['inputs']
    assert jobs[1]['config']['destination']['id'] == acquisition2
    assert 'test_context_value' in job2_inputs
    assert job2_inputs['test_context_value']['found'] == True
    assert job2_inputs['test_context_value']['value'] == 'project_context_value'

    # test batch.state after calling run
    r = as_admin.get('/batch/' + batch_id)
    assert r.json()['state'] == 'running'

    # Cleanup
    r = as_admin.delete('/gears/' + gear)
    assert r.ok

    # must remove jobs manually because gears were added manually
    api_db.jobs.remove({'gear_id': {'$in': [gear]}})


def test_optional_input_batch(data_builder, default_payload, as_admin, as_root, file_form, randstr, api_db):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    session2 = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)

    as_admin.post('/acquisitions/' + acquisition + '/files', files={
        'file': ('test.txt', 'test\ncontent\n')})

    as_admin.post('/acquisitions/' + acquisition2 + '/files', files={
        'file': ('test2.txt', 'test\ncontent2\n')})
    as_admin.post('/acquisitions/' + acquisition2 + '/files', files={
        'file': ('test2.csv', 'test\ncsv2\n')})

    gear_name = randstr()
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = gear_name
    gear_doc['gear']['inputs'] = {
        'text': {
            'base': 'file',
            'name': {'pattern': '^.*.txt$'},
            'size': {'maximum': 100000}
        },
        'csv': {
            'base': 'file',
            'name': {'pattern': '^.*.csv$'},
            'size': {'maximum': 100000},
            'optional': True
        }
    }

    r = as_root.post('/gears/' + gear_name, json=gear_doc)
    assert r.ok
    gear = r.json()['_id']

    # create a batch without policy
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.status_code == 400

    # create a batch with invalid policy
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        "optional_input_policy": "not_policy",
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.status_code == 400

    # create a batch requiring optional inputs
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'optional_input_policy': 'required',
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch1 = r.json()

    assert len(batch1['matched']) == 1
    assert batch1['matched'][0]['_id'] == acquisition2
    assert 'inputs' not in batch1['matched'][0]

    batch_id = batch1['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job config for inputs
    jobs = r.json()
    job1_inputs = jobs[0]['config']['inputs']
    assert len(job1_inputs) == 2
    assert 'text' in job1_inputs
    assert 'csv' in job1_inputs

    # create a batch not requiring optional inputs
    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'optional_input_policy': 'flexible',
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch1 = r.json()

    assert len(batch1['matched']) == 2
    assert batch1['matched'][0]['_id'] == acquisition
    assert 'inputs' not in batch1['matched'][0]
    assert batch1['matched'][1]['_id'] == acquisition2
    assert 'inputs' not in batch1['matched'][1]

    batch_id = batch1['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job configs for inputs
    jobs = r.json()
    job1_inputs = jobs[0]['config']['inputs']
    assert len(job1_inputs) == 1
    assert 'text' in job1_inputs

    job2_inputs = jobs[1]['config']['inputs']
    assert len(job2_inputs) == 2
    assert 'text' in job2_inputs
    assert 'csv' in job2_inputs

    # Test ignore_optional_inputs param so that ambiguity is not a problem for optional inputs
    as_admin.post('/acquisitions/' + acquisition2 + '/files', files={
        'file': ('test2_2.csv', 'test\ncsv2_2\n')})

    r = as_admin.post('/batch', json={
        'gear_id': gear,
        'optional_input_policy': 'ignored',
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch2 = r.json()

    assert len(batch2['matched']) == 2
    assert batch2['matched'][0]['_id'] == acquisition
    assert 'inputs' not in batch2['matched'][0]
    assert batch2['matched'][1]['_id'] == acquisition2
    assert 'inputs' not in batch2['matched'][1]

    batch_id = batch2['_id']

    # run batch
    r = as_admin.post('/batch/' + batch_id + '/run')
    assert r.ok

    # Check job configs for inputs
    jobs = r.json()
    job1_inputs = jobs[0]['config']['inputs']
    assert len(job1_inputs) == 1
    assert 'text' in job1_inputs

    job2_inputs = jobs[1]['config']['inputs']
    assert len(job2_inputs) == 1
    assert 'text' in job2_inputs

    # Try creating batch with optional inputs and api-key input
    gear_doc['gear']['inputs'] = {
        'text': {
            'base': 'file',
            'name': {'pattern': '^.*.txt$'},
            'size': {'maximum': 100000}
        },
        'csv': {
            'base': 'file',
            'name': {'pattern': '^.*.csv$'},
            'size': {'maximum': 100000},
            'optional': True
        },
        'api_key': {
            'base': 'api-key'
        }
    }
    gear_doc['gear']['version'] = '1'

    r = as_root.post('/gears/' + gear_name, json=gear_doc)
    assert r.ok
    gear_v1 = r.json()['_id']

    # create a batch not requiring optional inputs
    r = as_admin.post('/batch', json={
        'gear_id': gear_v1,
        'optional_input_policy': 'flexible',
        'targets': [{'type': 'session', 'id': session}, {'type': 'session', 'id': session2}]
    })
    assert r.ok
    batch3 = r.json()
    r = as_admin.post('/batch/' + batch3['_id'] + '/run')
    assert r.ok


    # Cleanup
    r = as_root.delete('/gears/' + gear)
    assert r.ok
    r = as_root.delete('/gears/' + gear_v1)
    assert r.ok

    # must remove jobs manually because gears were added manually
    api_db.jobs.remove({'gear_id': {'$in': [gear, gear_v1]}})
