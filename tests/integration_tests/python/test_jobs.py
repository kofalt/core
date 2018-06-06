import copy

import bson
import datetime

def test_jobs_access(as_user):
    r = as_user.get('/jobs/next')
    assert r.status_code == 403

    r = as_user.get('/jobs/stats')
    assert r.status_code == 403

    r = as_user.get('/jobs/pending')
    assert r.status_code == 403

    r = as_user.post('/jobs/reap')
    assert r.status_code == 403

    r = as_user.get('/jobs/test-job')
    assert r.status_code == 403

    r = as_user.get('/jobs/test-job/config.json')
    assert r.status_code == 403


def test_jobs(data_builder, default_payload, as_public, as_user, as_admin, as_root, api_db, file_form):

    # Dupe of test_queue.py
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    invalid_gear = data_builder.create_gear(gear={'custom': {'flywheel': {'invalid': True}}})
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
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
        'config': { 'two-digit multiple of ten': 20 },
        'destination': {
            'type': 'acquisition',
            'id': acquisition
        },
        'tags': [ 'test-tag' ]
    }

    # try to add job w/ non-existent gear
    job0 = copy.deepcopy(job_data)
    job0['gear_id'] = '000000000000000000000000'
    r = as_admin.post('/jobs/add', json=job0)
    assert r.status_code == 400

    # add job with explicit destination
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job1_id = r.json()['_id']

    # get job
    r = as_root.get('/jobs/' + job1_id)
    assert r.ok

    # get job log (empty)
    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert r.json()['logs'] == []

    # try to add job log w/o root
    # needed to use as_user because root = true for as_admin
    job_logs = [{'fd': 1, 'msg': 'Hello'}, {'fd': 2, 'msg': 'World'}]
    r = as_user.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.status_code == 403

    # try to add job log to non-existent job
    r = as_root.post('/jobs/000000000000000000000000/logs', json=job_logs)
    assert r.status_code == 404

    # get job log as text w/o logs
    r = as_admin.get('/jobs/' + job1_id + '/logs/text')
    assert r.ok
    assert r.text == '<span class="fd--1">No logs were found for this job.</span>'

    # get job log as html w/o logs
    r = as_admin.get('/jobs/' + job1_id + '/logs/html')
    assert r.ok
    assert r.text == '<span class="fd--1">No logs were found for this job.</span>'

    # add job log
    r = as_root.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.ok

    # try to get job log of non-existent job
    r = as_admin.get('/jobs/000000000000000000000000/logs')
    assert r.status_code == 404

    # get job log (non-empty)
    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert len(r.json()['logs']) == 2

    # add same logs again (for testing text/html logs)
    r = as_root.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.ok

    # get job log as text
    r = as_admin.get('/jobs/' + job1_id + '/logs/text')
    assert r.ok
    assert r.text == 2 * ''.join(log['msg'] for log in job_logs)

    # get job log as html
    r = as_admin.get('/jobs/' + job1_id + '/logs/html')
    assert r.ok
    assert r.text == 2 * ''.join('<span class="fd-{fd}">{msg}</span>\n'.format(**log) for log in job_logs)

    # get job config
    r = as_root.get('/jobs/' + job1_id + '/config.json')
    assert r.ok

    # try to cancel job w/o permission (different user)
    r = as_user.put('/jobs/' + job1_id, json={'state': 'cancelled'})
    assert r.status_code == 403

    # try to update job (user may only cancel)
    api_db.jobs.update_one({'_id': bson.ObjectId(job1_id)}, {'$set': {'origin.id': 'user@user.com'}})
    r = as_user.put('/jobs/' + job1_id, json={'test': 'invalid'})
    assert r.status_code == 403

    # add job with implicit destination
    job2 = copy.deepcopy(job_data)
    del job2['destination']
    r = as_admin.post('/jobs/add', json=job2)
    assert r.ok

    # add job with invalid gear
    job3 = copy.deepcopy(job_data)
    job3['gear_id'] = invalid_gear

    r = as_admin.post('/jobs/add', json=job3)
    assert r.status_code == 400

    # get next job - with nonexistent tag
    r = as_root.get('/jobs/next', params={'tags': 'fake-tag'})
    assert r.status_code == 400

    # get next job with peek
    r = as_root.get('/jobs/next', params={'tags': 'test-tag', 'peek': True})
    assert r.ok
    next_job_id = r.json()['id']

    # get next job
    r = as_root.get('/jobs/next', params={'tags': 'test-tag'})
    assert r.ok
    next_job_id = r.json()['id']

    # set next job to failed
    r = as_root.put('/jobs/' + next_job_id, json={'state': 'failed'})
    assert r.ok

    # retry failed job
    r = as_root.post('/jobs/' + next_job_id + '/retry')
    assert r.ok

    # get next job as admin
    r = as_admin.get('/jobs/next', params={'tags': 'test-tag'})
    assert r.ok
    next_job_id = r.json()['id']

    # set next job to failed
    r = as_root.put('/jobs/' + next_job_id, json={'state': 'failed'})
    assert r.ok

    # retry failed job w/o root
    r = as_admin.post('/jobs/' + next_job_id + '/retry')
    assert r.ok

    # set as_user perms to ro
    r = as_user.get('/users/self')
    assert r.ok
    uid = r.json()['_id']

    r = as_admin.post('/projects/' + project + '/permissions', json={
        '_id': uid,
        'access': 'ro'
    })
    assert r.ok

    # try to add job without rw
    r = as_user.post('/jobs/add', json=job_data)
    assert r.status_code == 403

    # set as_user perms to rw
    r = as_admin.put('/projects/' + project + '/permissions/' + uid, json={
        'access': 'rw'
    })
    assert r.ok

    # add job with rw
    r = as_user.post('/jobs/add', json=job_data)
    assert r.ok
    job_rw_id = r.json()['_id']

    # get next job as admin
    r = as_admin.get('/jobs/next', params={'tags': 'test-tag'})
    assert r.ok
    job_rw_id = r.json()['id']

    # try to add job with no inputs and no destination
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {}
    gear2 = data_builder.create_gear(gear=gear_doc)

    job5 = copy.deepcopy(job_data)
    job5['gear_id'] = gear2
    job5.pop('inputs')
    job5.pop('destination')

    r = as_admin.post('/jobs/add', json=job5)
    assert r.status_code == 400

    # try to add job with input type that is not file nor api-key
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'made-up'
        }
    }
    gear3 = str(api_db.gears.insert(gear_doc))

    job6 = copy.deepcopy(job_data)
    job6['gear_id'] = gear3

    r = as_admin.post('/jobs/add', json=job6)
    assert r.status_code == 500

    assert as_root.delete('/gears/' + gear3).ok

    # Attempt to set a malformed file reference as input
    job7 = copy.deepcopy(job_data)
    job7['inputs'] = {
        'dicom': {
                # missing type
                'id': acquisition,
                'name': 'test.zip'
        }
    }
    r = as_admin.post('/jobs/add', json=job7)
    assert r.status_code == 400

    # Insert non-running job into database
    job_instance = {
        "_id" : bson.ObjectId("5a007cdb0f352600d94c845f"),
        "inputs" : [{
            "input": 'dicom',
            'type': 'acquisition',
            'id': acquisition,
            'name': 'test.zip'
        }],
        # Set attempt to 5 so that job isn't retried, throwing off the usage report tests
        "attempt" : 5,
        "tags" : [
            "ad-hoc"
        ],
        "destination" : {
            "type" : "acquisition",
            "id" : acquisition
        },
        "modified" : datetime.datetime(1980, 1, 1),
        "created" : datetime.datetime(1980, 1, 1),
        "produced_metadata" : {},
        "saved_files" : [],
        "state" : "running",
        "gear_id" : gear3,
        "batch" : None,
    }
    api_db.jobs.insert_one(job_instance)
    r = as_root.post('/jobs/reap')
    assert r.ok
    assert r.json().get('orphaned') == 1
    r = as_admin.get('/jobs/'+str(job_instance['_id'])+'/logs')
    assert r.ok
    assert "The job did not report in for a long time and was canceled." in [log["msg"] for log in r.json()['logs']]
    api_db.jobs.delete_one({"_id": bson.ObjectId("5a007cdb0f352600d94c845f")})

    r = as_admin.get('/jobs/stats')
    assert r.ok
    r = as_admin.get('/jobs/pending')
    assert r.ok
    r = as_admin.get('/jobs/pending', params={'tags': 'auto,unused'})
    assert r.ok
    r = as_admin.get('/jobs/stats', params={'all': '1'})
    assert r.ok
    r = as_admin.get('/jobs/stats', params={'tags': 'auto,unused', 'last': '2'})
    assert r.ok


def test_failed_job_output(data_builder, default_payload, as_user, as_admin, as_drone, api_db, file_form):
    # create gear
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    gear2 = data_builder.create_gear()
    gear2_name = as_admin.get('/gears/' + gear2).json()['gear']['name']
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip'))
    assert r.ok

    # create rule for text files
    r = as_admin.post('/projects/' + project + '/rules', json={
        'alg': gear2_name,
        'name': 'text-trigger',
        'any': [],
        'not': [],
        'all': [{'type': 'file.type', 'value': 'text'}]
    })
    assert r.ok

    # create job
    r = as_admin.post('/jobs/add', json={
        'gear_id': gear,
        'inputs': {
            'dicom': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.zip'
            }
        },
        'config': {},
        'destination': {
            'type': 'acquisition',
            'id': acquisition
        }
    })
    assert r.ok
    job = r.json()['_id']
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job + '/prepare-complete', json={'success': False, 'elapsed': -1})
    assert r.ok

    # verify that job ticket has been created
    job_ticket = api_db.job_tickets.find_one({'job': job})
    assert job_ticket['success'] == False

    # engine upload
    r = as_drone.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'job_ticket': job_ticket['_id']},
        files=file_form('result.txt', meta={
            'project': {
                'label': 'engine project',
                'info': {'test': 'p'}
            },
            'session': {
                'label': 'engine session',
                'subject': {'code': 'engine subject'},
                'info': {'test': 's'}
            },
            'acquisition': {
                'label': 'engine acquisition',
                'timestamp': '2016-06-20T21:57:36+00:00',
                'info': {'test': 'a'},
                'files': [{
                    'name': 'result.txt',
                    'type': 'text',
                    'info': {'test': 'f0'}
                }]
            }
        })
    )
    assert r.ok

    # verify job was transitioned to failed state
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'failed'

    # verify metadata wasn't applied
    acq = as_admin.get('/acquisitions/' + acquisition).json()
    assert 'test' not in acq.get('info', {})

    # verify uploaded file got marked w/ 'from_failed_job'
    result_file = acq['files'][-1]
    assert 'from_failed_job' in result_file
    assert result_file['from_failed_job'] == True

    # verify that no jobs were spawned for failed files
    jobs = [j for j in api_db.jobs.find({'gear_id': gear2})]
    assert len(jobs) == 0

    # try to accept failed output - user has no access to destination
    r = as_user.post('/jobs/' + job + '/accept-failed-output')
    assert r.status_code == 403

    # accept failed output
    r = as_admin.post('/jobs/' + job + '/accept-failed-output')
    assert r.ok

    # verify job is marked w/ 'failed_output_accepted'
    job_doc = as_admin.get('/jobs/' + job).json()
    assert 'failed_output_accepted' in job_doc
    assert job_doc['failed_output_accepted'] == True

    # verify metadata was applied on hierarchy
    acq = as_admin.get('/acquisitions/' + acquisition).json()
    assert 'test' in acq.get('info', {})

    # verify uploaded file isn't marked anymore
    result_file = acq['files'][-1]
    assert 'from_failed_job' not in result_file

    # verify that a job was spawned for accepted files
    jobs = [j for j in api_db.jobs.find({'gear_id': gear2})]
    assert len(jobs) == 1


def test_job_state_transition_from_ticket(data_builder, default_payload, as_admin, as_drone, api_db, file_form):
    # create gear
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {'dicom': {'base': 'file'}}
    gear = data_builder.create_gear(gear=gear_doc)

    # create acq with file (for input)
    acquisition = data_builder.create_acquisition()
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip'))
    assert r.ok

    # create job
    r = as_admin.post('/jobs/add', json={
        'gear_id': gear,
        'config': {},
        'inputs': {'dicom': {'type': 'acquisition', 'id': acquisition, 'name': 'test.zip'}},
        'destination': {'type': 'acquisition', 'id': acquisition}
    })
    assert r.ok
    job = r.json()['_id']
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job + '/prepare-complete', json={'success': True, 'elapsed': 3})
    assert r.ok
    job_ticket = r.json()['ticket']

    # engine upload (should trigger state transition based on ticket)
    r = as_drone.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={
            'acquisition': {'files': [{'name': 'result.txt', 'type': 'text'}]}
        })
    )
    assert r.ok

    # verify job was transitioned to complete state
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'complete'

    # test with success: False
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})
    api_db.job_tickets.update_one({'_id': bson.ObjectId(job_ticket)}, {'$set': {'success': False}})
    r = as_drone.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={
            'acquisition': {'files': [{'name': 'result.txt', 'type': 'text'}]}
        })
    )
    assert r.ok
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'failed'

    # create session, analysis and job
    session = data_builder.create_session()
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'online',
        'job': {'gear_id': gear,
                'inputs': {'dicom': {'type': 'acquisition', 'id': acquisition, 'name': 'test.zip'}}}
    })
    assert r.ok
    analysis = r.json()['_id']

    r = as_admin.get('/analyses/' + analysis)
    assert r.ok
    job = r.json().get('job')
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job + '/prepare-complete', json={'success': True, 'elapsed': 3})
    assert r.ok
    job_ticket = r.json()['ticket']

    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={'type': 'text'}))
    assert r.ok

    # verify job was transitioned to complete state
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'complete'

    # test with success: False
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})
    api_db.job_tickets.update_one({'_id': bson.ObjectId(job_ticket)}, {'$set': {'success': False}})
    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={'type': 'text'}))
    assert r.ok
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'failed'


def test_analysis_job_creation_errors(data_builder, default_payload, as_admin, file_form):
    project = data_builder.create_project()
    session = data_builder.create_session()
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'csv': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    # Add project file
    r = as_admin.post('/projects/' + project + '/files', files=file_form('job_1.csv'))
    assert r.ok

    # ensure analysis with improper gear id is not created
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'with-job',
        'job': {
            # no gear id
            'inputs': {
                'csv': {'type': 'project', 'id': project, 'name': 'job_1.csv'}
            }
        }
    })
    assert r.status_code == 400
    assert len(as_admin.get('/sessions/' + session).json().get('analyses', [])) == 0

    # ensure analysis with improper inputs is not created
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'with-job',
        'job': {
            'gear_id': gear,
            'inputs': {
                'made-up': {'type': 'project', 'id': project, 'name': 'job_1.csv'}
            }
        }
    })
    assert r.status_code == 400
    assert len(as_admin.get('/sessions/' + session).json().get('analyses', [])) == 0

def test_job_context(data_builder, default_payload, as_admin, as_root, file_form):
    # Dupe of test_queue.py
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'zip': {
            'base': 'file'
        },
        'test_context_value': {
            'base': 'context'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    job_data = {
        'gear_id': gear,
        'inputs': {
            'zip': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.zip'
            }
        },
        'tags': [ 'test-tag' ]
    }

    # add job without context value
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job1_id = r.json()['_id']

    # get job
    r = as_root.get('/jobs/' + job1_id)
    assert r.ok
    r_job = r.json()
    r_inputs = r_job['config']['inputs']
    assert 'test_context_value' in r_inputs
    assert r_inputs['test_context_value']['base'] == 'context'
    assert r_inputs['test_context_value']['found'] == False

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

    # add job with project context value
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job2_id = r.json()['_id']

    # get job
    r = as_root.get('/jobs/' + job2_id)
    assert r.ok
    r_job = r.json()
    r_inputs = r_job['config']['inputs']
    assert 'test_context_value' in r_inputs
    assert r_inputs['test_context_value']['base'] == 'context'
    assert r_inputs['test_context_value']['found'] == True
    assert r_inputs['test_context_value']['value'] == 'project_context_value'

    # Override context at session level
    r = as_admin.post('/sessions/' + session + '/info', json={
        'set': {
            'context': {
                'test_context_value': {
                    'session_value': 3
                }
            }
        }
    })
    assert r.ok

    # add job with session context value
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job3_id = r.json()['_id']

    # get job
    r = as_root.get('/jobs/' + job3_id)
    assert r.ok
    r_job = r.json()
    r_inputs = r_job['config']['inputs']
    assert 'test_context_value' in r_inputs
    assert r_inputs['test_context_value']['base'] == 'context'
    assert r_inputs['test_context_value']['found'] == True
    assert r_inputs['test_context_value']['value'] == { 'session_value': 3 }


def test_job_api_key(data_builder, default_payload, as_public, as_admin, as_root, api_db, file_form):

    acquisition = data_builder.create_acquisition()
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    # Add job with gear that uses api-key base type and get config
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        },
        'api_key': {
            'base': 'api-key'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    job_data = {
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


    job1 = copy.deepcopy(job_data)
    job1['gear_id'] = gear

    r = as_admin.post('/jobs/add', json=job1)
    assert r.status_code == 200
    job_id = r.json()['_id']

    # start job
    r = as_root.put('/jobs/' + job_id, json={'state': 'running'})
    assert r.ok

    # get config
    r = as_root.get('/jobs/'+ job_id +'/config.json')
    assert r.ok
    config = r.json()

    assert type(config['inputs']['dicom']) is dict
    assert config['destination']['id'] == acquisition
    assert type(config['config']) is dict
    api_key = config['inputs']['api_key']['key']

    # ensure api_key works
    as_job_key = as_public
    as_job_key.headers.update({'Authorization': 'scitran-user ' + api_key})
    r = as_job_key.get('/users/self')
    assert r.ok

    # complete job and ensure API key no longer works
    r = as_root.put('/jobs/' + job_id, json={'state': 'complete'})
    assert r.ok

    r = as_job_key.get('/users/self')
    assert r.status_code == 401

    ##
    # Ensure API key is generated for retried job
    ##

    job2 = copy.deepcopy(job_data)
    job2['gear_id'] = gear

    r = as_admin.post('/jobs/add', json=job2)
    assert r.status_code == 200
    job_id = r.json()['_id']

    # start job
    r = as_root.put('/jobs/' + job_id, json={'state': 'running'})
    assert r.ok

    # set next job to failed
    r = as_root.put('/jobs/' + job_id, json={'state': 'failed'})
    assert r.ok

    # retry failed job
    r = as_root.post('/jobs/' + job_id + '/retry')
    assert r.ok

    # get next job as admin
    r = as_root.get('/jobs/next')
    assert r.ok
    retried_job_id = r.json()['id']

    # get config
    r = as_root.get('/jobs/'+ retried_job_id +'/config.json')
    assert r.ok
    config = r.json()

    assert type(config['inputs']['dicom']) is dict
    assert config['destination']['id'] == acquisition
    assert type(config['config']) is dict
    api_key = config['inputs']['api_key']['key']

    # ensure api_key works
    as_job_key = as_public
    as_job_key.headers.update({'Authorization': 'scitran-user ' + api_key})
    r = as_job_key.get('/users/self')
    assert r.ok

    # complete job and ensure API key no longer works
    r = as_root.put('/jobs/' + retried_job_id, json={'state': 'complete'})
    assert r.ok

    r = as_job_key.get('/users/self')
    assert r.status_code == 401

