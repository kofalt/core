import copy

import bson
import datetime

def test_jobs_access(as_user):
    r = as_user.get('/jobs/next')
    assert r.status_code == 403

    r = as_user.get('/jobs/stats')
    assert r.status_code == 403

    r = as_user.post('/jobs/reap')
    assert r.status_code == 403
    r = as_user.get('/jobs/test-job')
    assert r.status_code == 403

    r = as_user.get('/jobs/test-job/config.json')
    assert r.status_code == 403

def test_jobs(data_builder, default_payload, as_public, as_user, as_admin, api_db, file_form):
    """
    Can be removed in favor of test_jobs_ask when /jobs/next is retired.
    """

    # Dupe of test_queue.py
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    invalid_gear = data_builder.create_gear(gear={'custom': {'flywheel': {'invalid': True}}})
    group = data_builder.create_group()
    project = data_builder.create_project(group=group)
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    # Create ad-hoc analysis
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'offline',
        'inputs': [{'type': 'acquisition', 'id': acquisition, 'name': 'test.zip'}]
    })
    assert r.ok
    analysis = r.json()['_id']
    # Manually upload outputs
    r = as_admin.post('/analyses/' + analysis + '/files', files=file_form('output1.csv', 'output2.csv', meta=[
        {'name': 'output1.csv', 'info': {'foo': 'foo'}},
        {'name': 'output2.csv', 'info': {'bar': 'bar'}},
    ]))
    assert r.ok

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

    # try to add job with analysis as explicit destination
    job_data['destination'] = {
        'type': 'analysis',
        'id': analysis
    }
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 400


    job_data['destination'] = {
        'type': 'acquisition',
        'id': acquisition
    }

    # try to add job w/ non-existent gear
    job0 = copy.deepcopy(job_data)
    job0['gear_id'] = '000000000000000000000000'
    r = as_admin.post('/jobs/add', json=job0)
    assert r.status_code == 404

    # try to add job without login
    r = as_public.post('/jobs/add', json=job_data)
    assert r.status_code == 403

    # add job with explicit destination
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job1_id = r.json()['_id']

    # get job
    r = as_admin.get('/jobs/' + job1_id)
    assert r.ok

    job = r.json()
    assert job['gear_info']['name']
    assert job['gear_info']['version'] == '0.0.1'

    # get job log (empty)
    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert r.json()['logs'] == []

    # get job as admin without permissions to destination
    admin_id = as_admin.get('/users/self').json()['_id']
    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.delete('/projects/' + project + '/permissions/' + admin_id).ok

    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok

    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': admin_id
    }).ok

    # make sure user with permissions to the project can view it
    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': user_id
    }).ok

    r = as_user.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert as_admin.delete('/projects/' + project + '/permissions/' + user_id).ok

    # try to add job log w/o root
    # needed to use as_user because root = true for as_admin
    job_logs = [{'fd': 1, 'msg': 'Hello'}, {'fd': 2, 'msg': 'World'}]
    r = as_user.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.status_code == 403

    # try to add job log to non-existent job
    r = as_admin.post('/jobs/000000000000000000000000/logs', json=job_logs)
    assert r.status_code == 404

    # get job log as text w/o logs
    r = as_admin.get('/jobs/' + job1_id + '/logs/text')
    assert r.ok
    assert r.text == '<span class="fd--1">No logs were found for this job.</span>'

    # get job log as html w/o logs
    r = as_admin.get('/jobs/' + job1_id + '/logs/html')
    assert r.ok
    assert r.text == '<span class="fd--1">No logs were found for this job.</span>'

    # start job (Adds logs)
    r = as_admin.get('/jobs/next')
    assert r.ok
    started_job = r.json()
    assert started_job['transitions']['running'] == started_job['modified']
    assert started_job['parents']['group'] == group
    assert started_job['parents']['project'] == project
    assert started_job['parents']['session'] == session
    assert started_job['parents']['acquisition'] == acquisition
    assert started_job['profile']
    assert started_job['profile']['total_input_files'] == 1
    assert started_job['profile']['total_input_size_bytes'] > 1

    assert group in started_job['related_container_ids']
    assert project in started_job['related_container_ids']
    assert session in started_job['related_container_ids']
    assert acquisition in started_job['related_container_ids']

    assert started_job['id'] == job1_id

    # Must be admin to update job profile
    r = as_user.put('/jobs/' + job1_id + '/profile', json={
        'versions': {
            'engine': '1'
        }
    })
    assert r.status_code == 403

    # Test job exists
    r = as_admin.put('/jobs/5be1bcf6df0b1e3424a3b7ee/profile', json={
        'versions': {
            'engine': '9a12c5921a1d9206c2d82c0d1a60ebed3d55a338'
        }
    })
    assert r.status_code == 404

    # Test validation
    r = as_admin.put('/jobs/' + job1_id + '/profile', json={
        'widgets_consumed': 100
    })
    assert r.status_code == 400

    # Update job profile info
    r = as_admin.put('/jobs/' + job1_id + '/profile', json={
        'versions': {
            'engine': '9a12c5921a1d9206c2d82c0d1a60ebed3d55a338'
        },
        'executor': {
            'name': 'engine-625490',
            'host': '127.0.0.1',
            'instance_type': 'n1-standard-4',
            'cpu_cores': 4,
            'gpu': False,
            'memory_bytes': 15728640,
            'disk_bytes': 104857600,
            'swap_bytes': 31457280
        }
    })
    assert r.ok

    r = as_admin.get('/jobs/' + job1_id)
    assert r.ok
    updated_job = r.json()
    assert updated_job['profile']['versions']['engine'] == '9a12c5921a1d9206c2d82c0d1a60ebed3d55a338'

    assert updated_job['profile']['executor']['name'] == 'engine-625490'
    assert updated_job['profile']['executor']['host'] == '127.0.0.1'
    assert updated_job['profile']['executor']['instance_type'] == 'n1-standard-4'
    assert updated_job['profile']['executor']['cpu_cores'] == 4
    assert updated_job['profile']['executor']['gpu'] == False
    assert updated_job['profile']['executor']['memory_bytes'] == 15728640
    assert updated_job['profile']['executor']['disk_bytes'] == 104857600
    assert updated_job['profile']['executor']['swap_bytes'] == 31457280

    # add job log
    r = as_admin.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.ok

    # try to get job log of non-existent job
    r = as_admin.get('/jobs/000000000000000000000000/logs')
    assert r.status_code == 404

    # try to get job logs without access to inputs
    r = as_user.get('/jobs/' + job1_id + '/logs')
    assert r.status_code == 403

    # get job log (non-empty)
    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert len(r.json()['logs']) == 3

    # add same logs again (for testing text/html logs)
    r = as_admin.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.ok

    expected_job_logs = [{'fd': -1, 'msg': 'Gear Name: {}, Gear Version: {}\n'.format(job['gear_info']['name'], job['gear_info']['version'])}] + \
                        2 * job_logs

    # get job log as text
    r = as_admin.get('/jobs/' + job1_id + '/logs/text')
    assert r.ok
    assert r.text == ''.join(log['msg'] for log in expected_job_logs)

    # get job log as html
    r = as_admin.get('/jobs/' + job1_id + '/logs/html')
    assert r.ok
    assert r.text == ''.join('<span class="fd-{fd}">{msg}</span>\n'.format(fd=log.get('fd'), msg=log.get('msg').replace('\n', '<br/>\n')) for log in expected_job_logs)

    # get job config
    r = as_admin.get('/jobs/' + job1_id + '/config.json')
    assert r.ok

    # try to cancel job w/o permission (different user)
    r = as_user.put('/jobs/' + job1_id, json={'state': 'cancelled'})
    assert r.status_code == 403

    # try to update job (user may only cancel)
    api_db.jobs.update_one({'_id': bson.ObjectId(job1_id)}, {'$set': {'origin.id': 'user@user.com'}})
    r = as_user.put('/jobs/' + job1_id, json={'test': 'invalid'})
    assert r.status_code == 403

    # try to add job whos implicit destination is an analysis
    analyis_input_job_data = {
        'gear_id': gear,
        'inputs': {
            'dicom': {
                'type': 'analysis',
                'id': analysis,
                'name': 'output1.csv'
            }
        },
        'config': { 'two-digit multiple of ten': 20 },
        'tags': [ 'test-tag' ]
    }
    r = as_admin.post('/jobs/add', json=analyis_input_job_data)
    assert r.status_code == 400

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
    r = as_admin.get('/jobs/next', params={'tags': 'fake-tag'})
    assert r.status_code == 400

    # get next job - with excluding tag
    r = as_admin.get('/jobs/next', params={'tags': '!test-tag'})
    assert r.status_code == 400

    # get next job - with excluding tag overlap
    r = as_admin.get('/jobs/next', params={'tags': ['test-tag', '!test-tag']})
    assert r.status_code == 400

    # get next job with peek
    r = as_admin.get('/jobs/next', params={'tags': 'test-tag', 'peek': True})
    assert r.ok
    next_job_id_peek = r.json()['id']

    # get next job
    r = as_admin.get('/jobs/next', params={'tags': ['test-tag', '!fake-tag']})
    assert r.ok
    next_job_id = r.json()['id']
    assert next_job_id == next_job_id_peek

    # set next job to failed
    r = as_admin.put('/jobs/' + next_job_id, json={'state': 'failed', 'failure_reason': 'gear_failure'})
    assert r.ok

    # retry failed job
    r = as_admin.get('/jobs/' + next_job_id)
    assert r.ok
    failed_job = r.json()
    assert failed_job['transitions']['failed'] == failed_job['modified']
    assert failed_job['failure_reason'] == 'gear_failure'
    assert failed_job['profile']
    assert 'total_time_ms' in failed_job['profile']

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

    assert as_admin.delete('/gears/' + gear3).ok

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
    r = as_admin.post('/jobs/reap')
    assert r.ok
    assert r.json().get('orphaned') == 1
    r = as_admin.get('/jobs/'+str(job_instance['_id'])+'/logs')
    assert r.ok
    assert "The job did not report in for a long time and was canceled. " in [log["msg"] for log in r.json()['logs']]
    api_db.jobs.delete_one({"_id": bson.ObjectId("5a007cdb0f352600d94c845f")})

    r = as_admin.get('/jobs/stats')
    assert r.ok
    r = as_admin.get('/jobs/stats', params={'all': '1'})
    assert r.ok
    r = as_admin.get('/jobs/stats', params={'tags': 'auto,unused', 'last': '2'})
    assert r.ok

def question(struct):
    """
    Create a question with required values filled out.
    """

    empty_question = {
        "whitelist": { },
        "blacklist": { },
        # https://github.com/flywheel-io/gears/tree/master/spec#capabilities
        "capabilities": [ "networking" ],
        "return": { },
    }

    question = copy.deepcopy(empty_question)

    for x in struct:
        question[x] = struct[x]

    import json
    print(json.dumps(question, indent=4, sort_keys=True))

    return question

def test_jobs_ask(data_builder, default_payload, as_public, as_user, as_admin, api_db, file_form):
    """
    This can replace test_jobs when /jobs/next is retired.
    """

    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    invalid_gear = data_builder.create_gear(gear={'custom': {'flywheel': {'invalid': True}}})
    group = data_builder.create_group()
    project = data_builder.create_project(group=group)
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    # Create ad-hoc analysis
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'offline',
        'inputs': [{'type': 'acquisition', 'id': acquisition, 'name': 'test.zip'}]
    })
    assert r.ok
    analysis = r.json()['_id']
    # Manually upload outputs
    r = as_admin.post('/analyses/' + analysis + '/files', files=file_form('output1.csv', 'output2.csv', meta=[
        {'name': 'output1.csv', 'info': {'foo': 'foo'}},
        {'name': 'output2.csv', 'info': {'bar': 'bar'}},
    ]))
    assert r.ok

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

    # try to add job with analysis as explicit destination
    job_data['destination'] = {
        'type': 'analysis',
        'id': analysis
    }
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 400


    job_data['destination'] = {
        'type': 'acquisition',
        'id': acquisition
    }

    # try to add job w/ non-existent gear
    job0 = copy.deepcopy(job_data)
    job0['gear_id'] = '000000000000000000000000'
    r = as_admin.post('/jobs/add', json=job0)
    assert r.status_code == 404

    # try to add job without login
    r = as_public.post('/jobs/add', json=job_data)
    assert r.status_code == 403

    # add job with explicit destination
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job1_id = r.json()['_id']

    # get job
    r = as_admin.get('/jobs/' + job1_id)
    assert r.ok

    job = r.json()
    assert job['gear_info']['name']
    assert job['gear_info']['version'] == '0.0.1'

    # get job log (empty)
    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert r.json()['logs'] == []

    # get job as admin without permissions to destination
    admin_id = as_admin.get('/users/self').json()['_id']
    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.delete('/projects/' + project + '/permissions/' + admin_id).ok

    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok

    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': admin_id
    }).ok

    # make sure user with permissions to the project can view it
    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': user_id
    }).ok

    r = as_user.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert as_admin.delete('/projects/' + project + '/permissions/' + user_id).ok

    # try to add job log w/o root
    # needed to use as_user because root = true for as_admin
    job_logs = [{'fd': 1, 'msg': 'Hello'}, {'fd': 2, 'msg': 'World'}]
    r = as_user.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.status_code == 403

    # try to add job log to non-existent job
    r = as_admin.post('/jobs/000000000000000000000000/logs', json=job_logs)
    assert r.status_code == 404

    # get job log as text w/o logs
    r = as_admin.get('/jobs/' + job1_id + '/logs/text')
    assert r.ok
    assert r.text == '<span class="fd--1">No logs were found for this job.</span>'

    # get job log as html w/o logs
    r = as_admin.get('/jobs/' + job1_id + '/logs/html')
    assert r.ok
    assert r.text == '<span class="fd--1">No logs were found for this job.</span>'

    # start job (Adds logs)
    r = as_admin.post('/jobs/ask', json=question({
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    result = r.json()
    started_job = result['jobs'][0]
    assert started_job['transitions']['running'] == started_job['modified']
    assert started_job['parents']['group'] == group
    assert started_job['parents']['project'] == project
    assert started_job['parents']['session'] == session
    assert started_job['parents']['acquisition'] == acquisition
    assert started_job['profile']
    assert started_job['profile']['total_input_files'] == 1
    assert started_job['profile']['total_input_size_bytes'] > 1

    assert group in started_job['related_container_ids']
    assert project in started_job['related_container_ids']
    assert session in started_job['related_container_ids']
    assert acquisition in started_job['related_container_ids']

    assert started_job['id'] == job1_id

    # Must be admin to update job profile
    r = as_user.put('/jobs/' + job1_id + '/profile', json={
        'versions': {
            'engine': '1'
        }
    })
    assert r.status_code == 403

    # Test job exists
    r = as_admin.put('/jobs/5be1bcf6df0b1e3424a3b7ee/profile', json={
        'versions': {
            'engine': '9a12c5921a1d9206c2d82c0d1a60ebed3d55a338'
        }
    })
    assert r.status_code == 404

    # Test validation
    r = as_admin.put('/jobs/' + job1_id + '/profile', json={
        'widgets_consumed': 100
    })
    assert r.status_code == 400

    # Update job profile info
    r = as_admin.put('/jobs/' + job1_id + '/profile', json={
        'versions': {
            'engine': '9a12c5921a1d9206c2d82c0d1a60ebed3d55a338'
        },
        'executor': {
            'name': 'engine-625490',
            'host': '127.0.0.1',
            'instance_type': 'n1-standard-4',
            'cpu_cores': 4,
            'gpu': False,
            'memory_bytes': 15728640,
            'disk_bytes': 104857600,
            'swap_bytes': 31457280
        }
    })
    assert r.ok

    r = as_admin.get('/jobs/' + job1_id)
    assert r.ok
    updated_job = r.json()
    assert updated_job['profile']['versions']['engine'] == '9a12c5921a1d9206c2d82c0d1a60ebed3d55a338'

    assert updated_job['profile']['executor']['name'] == 'engine-625490'
    assert updated_job['profile']['executor']['host'] == '127.0.0.1'
    assert updated_job['profile']['executor']['instance_type'] == 'n1-standard-4'
    assert updated_job['profile']['executor']['cpu_cores'] == 4
    assert updated_job['profile']['executor']['gpu'] == False
    assert updated_job['profile']['executor']['memory_bytes'] == 15728640
    assert updated_job['profile']['executor']['disk_bytes'] == 104857600
    assert updated_job['profile']['executor']['swap_bytes'] == 31457280

    # add job log
    r = as_admin.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.ok

    # try to get job log of non-existent job
    r = as_admin.get('/jobs/000000000000000000000000/logs')
    assert r.status_code == 404

    # get job log (non-empty)
    r = as_admin.get('/jobs/' + job1_id + '/logs')
    assert r.ok
    assert len(r.json()['logs']) == 3

    # add same logs again (for testing text/html logs)
    r = as_admin.post('/jobs/' + job1_id + '/logs', json=job_logs)
    assert r.ok

    expected_job_logs = [{'fd': -1, 'msg': 'Gear Name: {}, Gear Version: {}\n'.format(job['gear_info']['name'], job['gear_info']['version'])}] + \
                        2 * job_logs

    # get job log as text
    r = as_admin.get('/jobs/' + job1_id + '/logs/text')
    assert r.ok
    assert r.text == ''.join(log['msg'] for log in expected_job_logs)

    # get job log as html
    r = as_admin.get('/jobs/' + job1_id + '/logs/html')
    assert r.ok
    assert r.text == ''.join('<span class="fd-{fd}">{msg}</span>\n'.format(fd=log.get('fd'), msg=log.get('msg').replace('\n', '<br/>\n')) for log in expected_job_logs)

    # get job config
    r = as_admin.get('/jobs/' + job1_id + '/config.json')
    assert r.ok

    # try to cancel job w/o permission (different user)
    r = as_user.put('/jobs/' + job1_id, json={'state': 'cancelled'})
    assert r.status_code == 403

    # try to update job (user may only cancel)
    api_db.jobs.update_one({'_id': bson.ObjectId(job1_id)}, {'$set': {'origin.id': 'user@user.com'}})
    r = as_user.put('/jobs/' + job1_id, json={'test': 'invalid'})
    assert r.status_code == 403

    # try to add job whos implicit destination is an analysis
    analyis_input_job_data = {
        'gear_id': gear,
        'inputs': {
            'dicom': {
                'type': 'analysis',
                'id': analysis,
                'name': 'output1.csv'
            }
        },
        'config': { 'two-digit multiple of ten': 20 },
        'tags': [ 'test-tag' ]
    }
    r = as_admin.post('/jobs/add', json=analyis_input_job_data)
    assert r.status_code == 400

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
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {
            'tag': ['fake-tag'],
        },
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    assert len(r.json()['jobs']) == 0

    # get next job - with excluding tag
    r = as_admin.post('/jobs/ask', json=question({
        'blacklist': {
            'tag': ['test-tag'],
        },
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    assert len(r.json()['jobs']) == 0

    # get next job - with excluding tag overlap
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {
            'tag': ['test-tag'],
        },
        'blacklist': {
            'tag': ['test-tag'],
        },
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    assert len(r.json()['jobs']) == 0

    # get next job with peek
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {
            'tag': ['test-tag']
        },
        'return': {
            'jobs': 1,
            'peek': True,
        },
    }))
    assert r.ok
    next_job_id_peek = r.json()['jobs'][0]['id']

    # get next job
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {
            'tag': ['test-tag'],
        },
        'blacklist': {
            'tag': ['fake-tag'],
        },
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    next_job_id = r.json()['jobs'][0]['id']
    assert next_job_id == next_job_id_peek

    # set next job to failed
    r = as_admin.put('/jobs/' + next_job_id, json={'state': 'failed', 'failure_reason': 'gear_failure'})
    assert r.ok

    # Get job and verify the 'failure' timestamp
    r = as_admin.get('/jobs/' + next_job_id)
    assert r.ok
    failed_job = r.json()
    assert failed_job['transitions']['failed'] == failed_job['modified']
    assert failed_job['failure_reason'] == 'gear_failure'
    assert failed_job['profile']
    assert 'total_time_ms' in failed_job['profile']

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
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {
            'tag': ['test-tag'],
        },
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    job_rw_id = r.json()['jobs'][0]['id']

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

    assert as_admin.delete('/gears/' + gear3).ok

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
    r = as_admin.post('/jobs/reap')
    assert r.ok
    assert r.json().get('orphaned') == 1
    r = as_admin.get('/jobs/'+str(job_instance['_id'])+'/logs')
    assert r.ok
    assert "The job did not report in for a long time and was canceled. " in [log["msg"] for log in r.json()['logs']]
    api_db.jobs.delete_one({"_id": bson.ObjectId("5a007cdb0f352600d94c845f")})

    r = as_admin.get('/jobs/stats')
    assert r.ok
    r = as_admin.get('/jobs/stats', params={'all': '1'})
    assert r.ok
    r = as_admin.get('/jobs/stats', params={'tags': 'auto,unused', 'last': '2'})
    assert r.ok

def test_jobs_capabilities(data_builder, default_payload, as_public, as_user, as_admin, api_db, file_form):

    # Test capabilities subset
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'whatever': {
            'base': 'file'
        }
    }
    gear_doc["capabilities"] = [ "networking", "extra" ]

    gear = data_builder.create_gear(gear=gear_doc)
    group = data_builder.create_group()
    project = data_builder.create_project(group=group)
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    job_data = {
        'gear_id': gear,
        'inputs': {
            'whatever': {
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

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id = r.json()['_id']

    # Check capabilities
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['gear_info']['capabilities'] == [ "networking", "extra" ]

    # Insufficient capabilities
    r = as_admin.post('/jobs/ask', json=question({
        'capabilities': [ ],
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    assert len(r.json()['jobs']) == 0

    # Insufficient capabilities
    r = as_admin.post('/jobs/ask', json=question({
        'capabilities': [ 'networking' ],
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    assert len(r.json()['jobs']) == 0

    # Sufficient capabilities
    r = as_admin.post('/jobs/ask', json=question({
        'capabilities': [ 'networking', 'extra', 'a' ],
        'return': {
            'jobs': 1,
        },
    }))
    assert r.ok
    result = r.json()
    assert len(result['jobs']) == 1
    assert result['jobs'][0]['id'] == job_id

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
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip'))
    assert r.ok

    # create rule for text files
    r = as_admin.post('/projects/' + project + '/rules', json={
        'gear_id': gear2,
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
    r = as_drone.post('/jobs/' + job + '/prepare-complete')
    assert r.ok

    # verify that job ticket has been created
    job_ticket = api_db.job_tickets.find_one({'job': job})
    assert job_ticket['timestamp']

    produced_metadata = {
        'project': {
            'label': 'engine project',
            'info': {'test': 'p'}
        },
        'session': {
            'label': 'engine session',
            'subject': {'code': 'engine subject', 'sex': 'male', 'age': 86400},
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
    }

    # engine upload
    r = as_drone.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'job_ticket': job_ticket['_id']},
        files=file_form('result.txt', meta=produced_metadata)
    )
    assert r.ok

    # Post complete
    r = as_drone.post('/jobs/' + job + '/complete', json={
        'success': False,
        'failure_reason': 'gear_failure',
        'profile': {
            'elapsed_time_ms': 36501,
            'preparation_time_ms': 2515,
            'upload_time_ms': 1017
        }
    })
    assert r.ok

    # verify job was transitioned to failed state
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'failed'
    assert job_doc['failure_reason'] == 'gear_failure'
    assert job_doc['profile']['upload_time_ms'] == 1017
    assert job_doc['profile']['preparation_time_ms'] == 2515
    assert job_doc['profile']['elapsed_time_ms'] == 36501

    # verify metadata was applied on hierarchy
    acq = as_admin.get('/acquisitions/' + acquisition).json()
    assert 'test' in acq.get('info', {})

    # Verify raw subject
    session = as_admin.get('/sessions/' + session).json()
    assert 'subject_raw' in session.get('info', {})
    assert session['info']['subject_raw'] == {'sex': 'male'}

    # Verify that produced metadata is preserved
    assert job_doc['produced_metadata'] == produced_metadata

    # verify uploaded file doesn't get marked w/ 'from_failed_job'
    result_file = acq['files'][-1]
    assert 'from_failed_job' not in result_file

    # verify that a job was spawned for uploaded files
    jobs = [j for j in api_db.jobs.find({'gear_id': gear2})]
    assert len(jobs) == 1

    # Verify job logs contains informational message about saved files
    expected_job_logs = [
        {'fd': -1, 'msg': 'The following outputs have been saved:\n'},
        {'fd': -1, 'msg': '  - result.txt\n'},
    ]

    r = as_admin.get('/jobs/' + job + '/logs')
    assert r.ok
    assert r.json()['logs'] == expected_job_logs

def test_job_state_transition_from_complete(data_builder, default_payload, as_admin, as_drone, api_db, file_form):
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
    r = as_drone.post('/jobs/' + job + '/prepare-complete')
    assert r.ok
    job_ticket = r.json()['ticket']

    # engine upload (should NOT trigger state transition based on ticket)
    r = as_drone.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={
            'acquisition': {'files': [{'name': 'result.txt', 'type': 'text'}]}
        })
    )
    assert r.ok

    # verify job is still running until complete is called
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'running'

    # Transition the job using /complete
    r = as_drone.post('/jobs/' + job + '/complete', json={
        'success': True,
        'profile': {
            'elapsed_time_ms': 3
        }
    })
    assert r.ok

    # verify job was transitioned to complete state
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'complete'
    assert job_doc['transitions']['complete']
    assert job_doc['transitions']['complete'] >= job_doc['created']
    assert job_doc['profile']
    assert job_doc['profile']['elapsed_time_ms'] == 3
    assert job_doc['profile']['total_output_files'] == 1
    assert job_doc['profile']['total_output_size_bytes'] > 0

    # test with success: False
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})
    r = as_drone.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={
            'acquisition': {'files': [{'name': 'result.txt', 'type': 'text'}]}
        })
    )
    assert r.ok
    r = as_drone.post('/jobs/' + job + '/complete?job_ticket_id=' + job_ticket, json={
        'success': False,
    })
    assert r.ok
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'failed'

    assert api_db.job_tickets.find_one({'_id': bson.ObjectId(job_ticket)}) is None

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

    # Start the job
    r = as_drone.get('/jobs/next')
    assert r.ok
    next_job = r.json()
    assert next_job['id'] == job
    assert next_job['state'] == 'running'
    assert next_job['transitions']['running']
    assert next_job['parents']['group']
    assert next_job['parents']['project']
    assert next_job['profile']['total_input_files'] == 1
    assert next_job['profile']['total_input_size_bytes'] > 1

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job + '/prepare-complete')
    assert r.ok
    job_ticket = r.json()['ticket']

    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={'type': 'text'}))
    assert r.ok

    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'running'

    # Transition the job using /complete
    r = as_drone.post('/jobs/' + job + '/complete', json={
        'success': True,
        'profile': {
            'elapsed_time_ms': 3
        }
    })
    assert r.ok

    # verify job was transitioned to complete state
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['state'] == 'complete'
    assert job_doc['transitions']['complete']
    assert job_doc['profile']['total_time_ms'] >= 0
    assert job_doc['profile']['elapsed_time_ms'] == 3
    assert job_doc['profile']['total_output_files'] == 1
    assert job_doc['profile']['total_output_size_bytes'] > 0

    # test with success: False
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'state': 'running'}})
    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.txt', meta={'type': 'text'}))
    assert r.ok
    r = as_drone.post('/jobs/' + job + '/complete', json={ 'success': False })
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

def test_job_context(data_builder, default_payload, as_admin, file_form):
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
        'tags': [ 'test-tag' ],
        'label': 'job-name'
    }

    # add job without context value
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job1_id = r.json()['_id']

    # get job label
    r = as_admin.get('/jobs/' + job1_id)
    job1_label = r.json()['label']
    assert job1_label == 'job-name'

    # get job
    r = as_admin.get('/jobs/' + job1_id)
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
    r = as_admin.get('/jobs/' + job2_id)
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
    r = as_admin.get('/jobs/' + job3_id)
    assert r.ok
    r_job = r.json()
    r_inputs = r_job['config']['inputs']
    assert 'test_context_value' in r_inputs
    assert r_inputs['test_context_value']['base'] == 'context'
    assert r_inputs['test_context_value']['found'] == True
    assert r_inputs['test_context_value']['value'] == { 'session_value': 3 }


def test_job_api_key(data_builder, default_payload, as_public, as_admin, as_user, api_db, file_form):
    project = data_builder.create_project()
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

    # get next job as admin
    r = as_admin.get('/jobs/next')
    assert r.ok

    # get config
    r = as_admin.get('/jobs/'+ job_id +'/config.json')
    assert r.ok
    config = r.json()

    assert type(config['inputs']['dicom']) is dict
    assert config['destination']['id'] == acquisition
    assert type(config['config']) is dict
    api_key = config['inputs']['api_key']['key']

    # check if job default label is empty string
    r = as_admin.get('/jobs/'+ job_id)
    assert r.json().get('label') == ""

    # ensure api_key works
    as_job_key = as_public
    as_job_key.headers.update({'Authorization': 'scitran-user ' + api_key})
    r = as_job_key.get('/users/self')
    assert r.ok

    # complete job and ensure API key no longer works
    r = as_admin.put('/jobs/' + job_id, json={'state': 'complete'})
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

    # get next job as admin
    r = as_admin.get('/jobs/next')
    assert r.ok

    # get config
    r = as_admin.get('/jobs/'+ job_id +'/config.json')
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

    # Make sure there are no jobs that are pending
    assert api_db.jobs.count({'state': 'pending'}) == 0

    # set job as one that should be orphaned
    api_db.jobs.update_one({'_id': bson.ObjectId(job_id)}, {'$set': {'modified': datetime.datetime(1980, 1, 1)}})

    # reap orphans
    r = as_admin.post('/jobs/reap')

    # Make sure there is only one job that is pending
    assert api_db.jobs.count({'state': 'pending'}) == 1

    # get next job as admin
    r = as_admin.get('/jobs/next')
    assert r.ok
    retried_job = r.json()
    retried_job_id = retried_job['id']
    assert retried_job['previous_job_id'] is not None

    # Ensure the attempt is bumped and the config uri is for the new job
    assert retried_job['attempt'] == 2
    found_config_uri = False
    for i in retried_job['request']['inputs']:
        if i['uri'] == '/jobs/' + retried_job_id + '/config.json':
            found_config_uri = True
            break
    assert found_config_uri

    # get config
    r = as_admin.get('/jobs/' + retried_job_id + '/config.json')
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
    r = as_admin.put('/jobs/' + retried_job_id, json={'state': 'complete'})
    assert r.ok

    r = as_job_key.get('/users/self')
    assert r.status_code == 401

    # Test that user can retry their own jobs, otherwise only admins can
    # Test rw user can't retry another's job
    user_id = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'rw'})
    assert r.ok

    r = as_user.post('/jobs/' + retried_job_id + '/retry', params={'ignoreState': True})
    assert r.status_code == 403

    # Start job as rw user
    r = as_user.post('/jobs/add', json=job1)
    assert r.ok
    job_id = r.json()['_id']

    # fail job and ensure API key no longer works
    r = as_admin.get('/jobs/next')
    assert r.ok
    r = as_admin.put('/jobs/' + job_id, json={'state': 'failed'})
    assert r.ok

    # Retry it as the user
    r = as_user.post('/jobs/' + job_id + '/retry')
    assert r.ok
    retried_job_id = r.json()['_id']

    r = as_admin.get('/jobs/next')
    assert r.ok
    r = as_admin.put('/jobs/' + retried_job_id, json={'state': 'failed'})
    assert r.ok

    # Make sure admins can retry any job
    r = as_admin.post('/jobs/' + retried_job_id + '/retry')
    assert r.ok

def test_job_tagging(data_builder, default_payload, as_admin, as_user, api_db, file_form):

    # Dupe of test_queue.py
    gear_doc = default_payload['gear']['gear']
    gear_name = 'gear-name'
    gear_doc['name'] = gear_name
    gear = data_builder.create_gear(gear=gear_doc)

    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()

    user_id = as_user.get('/users/self').json()['_id']
    as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'admin'})

    # Test the gear name tag with auto job rule
    rule = {
        'gear_id': gear,
        'name': 'job-trigger-rule',
        'any': [],
        'not': [],
        'all': [
            {'type': 'file.type', 'value': 'tabular data'}],
        'disabled': False
    }

    # add project rule
    r = as_user.post('/projects/' + project + '/rules', json=rule)
    assert r.ok
    rule_id = r.json()['_id']

    # create job
    # print gear_doc
    assert as_user.post('/acquisitions/' + acquisition + '/files', files=file_form('test.csv')).ok

    # Verify that job was created
    rule_jobs = [job for job in api_db.jobs.find({'gear_id': gear})]
    assert len(rule_jobs) == 1
    assert gear_name in rule_jobs[0].get('tags', [])

    # Test the gear name tag with manually adding the job
    job_data = {
        'gear_id': gear,
        'inputs': {
            'text': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.csv'
            }
        },
        'config': { 'two-digit multiple of ten': 20 },
        'destination': {
            'type': 'acquisition',
            'id': acquisition
        },
        # No gear name in tags
        'tags': [ 'test-tag' ]
    }

    # add job with explicit destination
    r = as_user.post('/jobs/add', json=job_data)
    assert r.ok
    manual_job_id = r.json()['_id']

    # get job
    r = as_admin.get('/jobs/' + manual_job_id)
    assert r.ok

    # Make sure that the job has the tag of the gear name
    manual_job = r.json()
    assert gear_name in manual_job['tags']

    # Test the gear name tag with job-based analysis
    r = as_user.post('/sessions/' + session + '/analyses', json={
        'label': 'online',
        'job': job_data
    })
    assert r.ok
    analysis_id = r.json()['_id']

    # Verify job was created with it
    r = as_user.get('/analyses/' + analysis_id)
    assert r.ok
    analysis_job_id = r.json().get('job')

    # get job
    r = as_admin.get('/jobs/' + analysis_job_id)
    assert r.ok

    # Make sure that the job has the tag of the gear name
    analysis_job = r.json()
    assert gear_name in analysis_job['tags']

def test_job_reap_ticketed_jobs(data_builder, default_payload, as_drone, as_admin, api_db, file_form):
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

    job = {
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

    r = as_admin.post('/jobs/add', json=job)
    assert r.status_code == 200
    job_id = r.json()['_id']

    r = as_admin.post('/jobs/add', json=job)
    assert r.status_code == 200
    job_id2 = r.json()['_id']

    # transition jobs to running
    r = as_drone.put('/jobs/' + job_id, json={'state': 'running'})
    assert r.ok

    r = as_drone.put('/jobs/' + job_id2, json={'state': 'running'})
    assert r.ok

    # Make sure there are no jobs that are pending
    assert api_db.jobs.count({'state': 'pending'}) == 0

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job_id + '/prepare-complete')
    assert r.ok

    # verify that job ticket has been created
    job_ticket = api_db.job_tickets.find_one({'job': job_id})

    # set job as one that should be orphaned
    api_db.jobs.update_one({'_id': bson.ObjectId(job_id)}, {'$set': {'modified': datetime.datetime(1980, 1, 1)}})
    api_db.jobs.update_one({'_id': bson.ObjectId(job_id2)}, {'$set': {'modified': datetime.datetime(1980, 1, 1)}})

    # reap orphans
    r = as_admin.post('/jobs/reap')

    # Make sure that exactly 1 job got restarted
    assert api_db.jobs.count({'state': 'pending'}) == 1

    # Ensure that our job is still running
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['state'] == 'running'

    # Ensure that our other job got marked as failed
    r = as_admin.get('/jobs/' + job_id2)
    assert r.ok
    assert r.json()['state'] == 'failed'

def test_job_requests(randstr, default_payload, data_builder, as_admin, as_drone, file_form):
    acquisition = data_builder.create_acquisition()
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    # Create gears
    gear_doc = default_payload['gear']['gear']
    gear_doc['name'] = randstr()
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file',
            'optional': True
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    gear_doc['name'] = randstr()
    not_url_gear = data_builder.create_gear(gear=gear_doc, exchange={'rootfs-url': '/api/gears/temp/5b840961bef39f0018b73e64'})

    job = {
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

    # Create jobs
    r = as_admin.post('/jobs/add', json=job)
    assert r.ok
    job_id = r.json()['_id']

    job['gear_id'] = not_url_gear

    r = as_admin.post('/jobs/add', json=job)
    assert r.ok
    not_url_job_id = r.json()['_id']

    # Start jobs
    r = as_drone.put('/jobs/' + job_id, json={'state': 'running'})
    assert r.ok

    r = as_drone.put('/jobs/' + not_url_job_id, json={'state': 'running'})
    assert r.ok

    # Check request inputs all have types
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    job_request_inputs = r.json()['request']['inputs']
    for request_input in job_request_inputs:
        assert request_input.get('type')
    r = as_admin.get('/jobs/' + not_url_job_id)
    assert r.ok
    not_url_job_request_inputs = r.json()['request']['inputs']
    for request_input in not_url_job_request_inputs:
        assert request_input.get('type')

def test_scoped_job_api_key(randstr, data_builder, default_payload, as_public, as_admin, file_form):
    gear_doc = default_payload['gear']['gear']

    rw_gear_name = randstr()
    gear_doc['name'] = rw_gear_name
    gear_doc['inputs'] = {
        "api_key": {
          "base": "api-key"
        }
    }
    rw_gear = data_builder.create_gear(gear=gear_doc)
    gear_name = randstr()
    gear_doc['name'] = gear_name
    gear_doc['inputs'] = {
        "api_key": {
          "base": "api-key",
          "read-only": True
        }
    }
    ro_gear = data_builder.create_gear(gear=gear_doc)

    group = data_builder.create_group()
    project = data_builder.create_project(public=False)
    session = data_builder.create_session(public=False)
    acquisition = data_builder.create_acquisition(public=False)
    # Create ad-hoc analysis
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'offline_1',
    })
    assert r.ok
    analysis = r.json()['_id']

    # Test the gear name tag with auto job rule
    rule = {
        'gear_id': rw_gear,
        'name': 'job-trigger-rule',
        'any': [],
        'not': [],
        'all': [
            {'type': 'file.type', 'value': 'tabular data'}],
        'disabled': False
    }

    # Try to add rule with gear that requires read-write api-key
    r = as_admin.post('/projects/' + project + '/rules', json=rule)
    assert r.status_code == 400

    rule['gear_id'] = ro_gear

    # add project rule
    r = as_admin.post('/projects/' + project + '/rules', json=rule)
    assert r.ok
    rule_id = r.json()['_id']

    # create job
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.csv')).ok

    # get next job as admin
    r = as_admin.get('/jobs/next')
    assert r.ok
    job_id = r.json()['id']

    # get config
    r = as_admin.get('/jobs/' + job_id + '/config.json')
    assert r.ok
    config = r.json()

    assert config['destination']['id'] == acquisition
    assert type(config['config']) is dict
    api_key = config['inputs']['api_key']['key']
    # print api_key
    # ensure api_key works
    as_job_key = as_public
    as_job_key.headers.update({'Authorization': 'scitran-user ' + api_key.split(':')[-1]})

    r = as_job_key.get('/projects/' + project)
    assert r.ok

    # ensure api_key can access public projects
    project_2 = data_builder.create_project(public=True)
    r = as_job_key.get('/projects/' + project_2)
    assert r.ok

    # ensure api_key can't access other non public projects
    project_3 = data_builder.create_project(public=False)
    r = as_job_key.get('/projects/' + project_3)
    assert r.status_code == 403

    # Test getting lists of containers
    session_2 = data_builder.create_session(project=project_3, public=False)
    acquisition_2 = data_builder.create_acquisition(session=session_2, public=False)
    assert as_admin.post('/acquisitions/' + acquisition_2 + '/files', files=file_form('test.csv')).ok
    # Create ad-hoc analysis
    r = as_admin.post('/sessions/' + session_2 + '/analyses', json={
        'label': 'offline_2',
    })
    assert r.ok
    analysis_2 = r.json()['_id']

    # test get_all
    r = as_job_key.get('/projects')
    assert r.ok
    assert len(r.json()) == 2

    r = as_job_key.get('/sessions')
    assert r.ok
    print r.json()
    assert len(r.json()) == 1
    assert session == r.json()[0]['_id']

    r = as_job_key.get('/acquisitions')
    assert r.ok
    assert len(r.json()) == 1
    assert acquisition == r.json()[0]['_id']

    r = as_job_key.get('/sessions/' + session + '/analyses')
    assert r.ok
    assert len(r.json()) == 1
    assert analysis == r.json()[0]['_id']

    r = as_job_key.get('/sessions/' + session_2 + '/analyses')
    assert r.status_code == 403

    # Download file in scope
    r = as_job_key.get('/acquisitions/' + acquisition + '/files/test.csv')
    assert r.ok

    # Try getting file from outside of scope
    r = as_job_key.get('/acquisitions/' + acquisition_2 + '/files/test.csv')
    assert r.status_code == 403

    # Try creating containers
    # r = as_job_key.post('/projects', json={'label': 'NewLabel', 'group': group})
    # assert r.status_code == 403
    r = as_job_key.post('/sessions', json={'label': 'NewLabel', 'project': project})
    assert r.status_code == 403
    r = as_job_key.post('/acquisitions', json={'label': 'NewLabel', 'session': session})
    assert r.status_code == 403
    # Create ad-hoc analysis
    r = as_job_key.post('/sessions/' + session + '/analyses', json={
        'label': 'offline_2'
    })
    assert r.status_code == 403

    # Try uploading a file
    r = as_job_key.post('/acquisitions/' + acquisition + '/files', files=file_form('test_1.csv'))
    assert r.status_code == 403

    # Try to modify different containers and sublists
    r = as_job_key.put('/projects/' + project, json={'label': 'NewLabel'})
    assert r.status_code == 403
    r = as_job_key.put('/sessions/' + session, json={'label': 'NewLabel'})
    assert r.status_code == 403
    r = as_job_key.put('/acquisitions/' + acquisition, json={'label': 'NewLabel'})
    assert r.status_code == 403
    r = as_job_key.put('/sessions/' + session + '/analyses/' + analysis, json={'label': 'NewLabel'})
    assert r.status_code == 403

    # Try modifying the info of a file in the scope
    r = as_job_key.post('/acquisitions/' + acquisition + '/files/test.csv/info', json={
        'set': {'Key': 'Value'}
    })
    assert r.status_code == 403

    # fail job and ensure API key no longer works
    r = as_admin.put('/jobs/' + job_id, json={'state': 'failed'})
    assert r.ok

    r = as_job_key.get('/projects/' + project)
    assert r.status_code == 401

    # Retry job
    r = as_admin.post('/jobs/' + job_id + '/retry')
    assert r.ok

    # get next job as admin
    r = as_admin.get('/jobs/next')
    assert r.ok
    retried_job_id = r.json()['id']

    # Make sure a new api key was created and the old one didn't magically start working again
    r = as_job_key.get('/projects/' + project)
    assert r.status_code == 401

    # get config
    r = as_admin.get('/jobs/' + retried_job_id + '/config.json')
    assert r.ok
    config = r.json()

    assert config['destination']['id'] == acquisition
    assert type(config['config']) is dict
    retried_api_key = config['inputs']['api_key']['key']
    # ensure api_key works
    as_job_key.headers.update({'Authorization': 'scitran-user ' + retried_api_key.split(':')[-1]})

    r = as_job_key.get('/projects/' + project)
    assert r.ok

def test_retry_jobs(data_builder, default_payload, as_admin, as_user, as_drone, file_form):
    # Not testing sdk jobs here, those are tested in the test_api_jobs
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    invalid_gear = data_builder.create_gear(gear={'custom': {'flywheel': {'invalid': True}}})
    project = data_builder.create_project()

    # Add user with r/w permission
    user_id = as_user.get('/users/self').json()['_id']
    r = as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'rw'})
    assert r.ok

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
    # add job with explicit destination
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job0_id = r.json()['_id']

    # get job0
    r = as_admin.get('/jobs/' + job0_id)
    assert r.ok
    job0 = r.json()

    # start job0 (Adds logs)
    r = as_admin.get('/jobs/next')
    assert r.ok

    # set job0 to failed
    r = as_admin.put('/jobs/' + job0_id, json={'state': 'failed'})
    assert r.ok

    # retry failed job0 w/o admin as job1
    r = as_user.post('/jobs/' + job0_id + '/retry')
    assert r.ok
    job1_id = r.json()['_id']

    # try retry failed job0 as job1 again
    r = as_admin.post('/jobs/' + job0_id + '/retry')
    assert r.status_code == 500

    # get job0 retried time
    r = as_admin.get('/jobs/' + job0_id)
    assert r.ok
    job0_retried_time = r.json().get('retried')
    assert job0_retried_time

    # get job1
    r = as_admin.get('/jobs/' + job1_id)
    assert r.ok
    job1 = r.json()

    # Make sure config, inputs, and destination are the same
    assert job0['inputs'] == job1['inputs']
    assert job0['destination'] == job1['destination']
    assert job0['config'] == job1['config']
    assert job0_retried_time == job1['created']

    # start job1 as admin
    r = as_admin.get('/jobs/next', params={'tags': 'test-tag'})
    assert r.ok

    # set job1 to failed
    r = as_admin.put('/jobs/' + job1_id, json={'state': 'failed'})
    assert r.ok

    r = as_admin.post('/jobs/' + job1_id + '/retry')
    assert r.ok

    # get job2 as admin
    r = as_admin.get('/jobs/next', params={'tags': 'test-tag'})
    assert r.ok
    job2_id = r.json()['id']

    # set job2 to running
    r = as_drone.put('/jobs/' + job2_id, json={'state': 'running'})
    assert r.ok

    # try retry runnning job2 as job3
    r = as_admin.post('/jobs/' + job2_id + '/retry')
    assert r.status_code == 400

    # try retry runnning job2 as job3 ignoring state
    r = as_admin.post('/jobs/' + job2_id + '/retry', params={'ignoreState': True})
    assert r.status_code == 400

    # set job2 to complete
    r = as_admin.put('/jobs/' + job2_id, json={'state': 'complete'})
    assert r.ok

    # try retry complete job2 as job3
    r = as_admin.post('/jobs/' + job2_id + '/retry')
    assert r.status_code == 400

    # retry complete job2 as job3
    r = as_admin.post('/jobs/' + job2_id + '/retry', params={'ignoreState': True})
    assert r.ok

    # get job3 as admin
    r = as_admin.get('/jobs/next', params={'tags': 'test-tag'})
    assert r.ok
    job3_id = r.json()['id']

    # set job3 to failed
    r = as_admin.put('/jobs/' + job3_id, json={'state': 'failed'})
    assert r.ok

    # Delete input file
    r = as_admin.delete('/acquisitions/' + acquisition + '/files/test.zip')
    assert r.ok

    # try retry failed job3
    r = as_admin.post('/jobs/' + job3_id + '/retry')
    assert r.status_code == 404

    # Use session input file, but delete destination acquisition
    assert as_admin.post('/sessions/' + session + '/files', files=file_form('session_test.zip')).ok

    job_data['inputs']['dicom'] = {
        'type': 'session',
        'id': session,
        'name': 'session_test.zip'
    }

    # add job with explicit destination
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job4_id = r.json()['_id']

    # start job3 (Adds logs)
    r = as_admin.get('/jobs/next')
    assert r.ok

    # set job4 to failed
    r = as_admin.put('/jobs/' + job4_id, json={'state': 'failed'})
    assert r.ok

    # Delete input file
    r = as_admin.delete('/acquisitions/' + acquisition)
    assert r.ok

    # try retry failed job4 as job5
    r = as_admin.post('/jobs/' + job4_id + '/retry')
    assert r.status_code == 404

def test_config_values(data_builder, default_payload, as_admin, file_form):

    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear_doc['config'] = {
        "str": {
            "type": "string",
            "optional": True
        },
        "int": {
            "type": "integer",
            "optional": True
        },
        "num": {
            "type": "number",
            "optional": True
        },
        "bool": {
            "type": "boolean",
            "optional": True
        }
    }
    gear_optional = data_builder.create_gear(gear=gear_doc)
    group = data_builder.create_group()
    project = data_builder.create_project(group=group)
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    job_data = {
        'gear_id': gear_optional,
        'inputs': {
            'dicom': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.zip'
            }
        },
        'config': {
            'str': None,
            'int': None,
            'num': None,
            'bool': None
        },
        'destination': {
            'type': 'acquisition',
            'id': acquisition
        },
        'tags': [ 'test-tag' ]
    }

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 422

    job_data['config'] = {}

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok

    # New gear without optional
    gear_doc['config'] = {
        "str": {
            "type": "string"
        },
        "int": {
            "type": "integer"
        },
        "num": {
            "type": "number"
        },
        "bool": {
            "type": "boolean"
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    job_data['gear_id'] = gear

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 422

    job_data['config'] = {
        'str': 'None',
        'int': 1,
        'num': 0,
        'bool': True
    }

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok

def test_job_detail(data_builder, default_payload, as_admin, as_user, as_drone, as_public, file_form, api_db):
    # Dupe of test_queue.py
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'zip': {
            'base': 'file'
        },
        'csv': {
            'base': 'file'
        },
        'test_context_value': {
            'base': 'context'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    group = data_builder.create_group(label='job-detail group')
    project = data_builder.create_project(label='job-detail project', info={
        'test_context_value': 3,
        'context': {
            'test_context_value': 'project_context_value'
        }
    })
    session = data_builder.create_session(label='job-detail session')
    acquisition = data_builder.create_acquisition(label='job-detail acquisition')

    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.csv')).ok

    assert as_admin.post('/acquisitions/' + acquisition + '/files/test.csv/info', json={
        'replace': {
            'input_key': 'input_value'
        }
    }).ok

    job_data = {
        'gear_id': gear,
        'inputs': {
            'zip': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.zip'
            },
            'csv': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.csv'
            }
        },
        'destination': {
            'type': 'session',
            'id': session
        }
    }

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job = r.json()['_id']

    r = as_admin.get('/jobs/next')
    assert r.ok
    started_job = r.json()
    assert started_job['id'] == job

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job + '/prepare-complete', json={'success': True, 'elapsed': 3})
    assert r.ok
    job_ticket = r.json()['ticket']

    r = as_drone.post('/engine',
        params={'level': 'session', 'id': session, 'job': job, 'job_ticket': job_ticket},
        files=file_form('result.zip', 'result.csv', meta={
            'session': {
                'files': [
                    {'name': 'result.zip', 'info': {'zip_key': 'zip_value'}},
                    {'name': 'result.csv', 'info': {'csv_key': 'csv_value'}},
                ]
            }
        }))
    assert r.ok

    # ===== Happy Path =====
    # Get job detail
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok
    r_detail = r.json()

    assert r_detail['id'] == job

    # Verify parent container info
    assert r_detail['parent_info']['group']['_id'] == group
    assert r_detail['parent_info']['group']['label'] == 'job-detail group'

    assert r_detail['parent_info']['project']['_id'] == project
    assert r_detail['parent_info']['project']['label'] == 'job-detail project'

    assert r_detail['parent_info']['subject']['label'] == 'unknown'

    assert r_detail['parent_info']['session']['_id'] == session
    assert r_detail['parent_info']['session']['label'] == 'job-detail session'

    assert 'acquisition' not in r_detail['parent_info']
    assert 'analysis' not in r_detail['parent_info']

    # Verify inputs
    zip_input = r_detail['inputs']['zip']
    assert zip_input['ref']['name'] == 'test.zip'
    assert zip_input['ref']['type'] == 'acquisition'
    assert zip_input['ref']['id'] == acquisition

    assert zip_input['object']['name'] == 'test.zip'
    assert zip_input['object']['type'] == 'archive'
    assert zip_input['object']['mimetype'] == 'application/zip'
    assert zip_input['object']['size'] > 0

    csv_input = r_detail['inputs']['csv']
    assert csv_input['ref']['name'] == 'test.csv'
    assert csv_input['ref']['type'] == 'acquisition'
    assert csv_input['ref']['id'] == acquisition

    assert csv_input['object']['name'] == 'test.csv'
    assert csv_input['object']['type'] == 'tabular data'
    assert csv_input['object']['mimetype'] == 'text/csv'
    assert csv_input['object']['size'] > 0

    # Verify outputs
    zip_out, csv_out = r_detail['outputs']
    if zip_out['ref']['name'] == 'result.csv':
        zip_out, csv_out = csv_out, zip_out

    assert zip_out['ref']['name'] == 'result.zip'
    assert zip_out['ref']['type'] == 'session'
    assert zip_out['ref']['id'] == session

    assert zip_out['object']['name'] == 'result.zip'
    assert zip_out['object']['type'] == 'archive'
    assert zip_out['object']['mimetype'] == 'application/zip'
    assert zip_out['object']['size'] > 0

    assert csv_out['ref']['name'] == 'result.csv'
    assert csv_out['ref']['type'] == 'session'
    assert csv_out['ref']['id'] == session

    assert csv_out['object']['name'] == 'result.csv'
    assert csv_out['object']['type'] == 'tabular data'
    assert csv_out['object']['mimetype'] == 'text/csv'
    assert csv_out['object']['size'] > 0

    # ===== Permission Checks ====
    r = as_public.get('/jobs/' + job + '/detail')
    assert r.status_code == 403

    r = as_user.get('/jobs/' + job + '/detail')
    assert r.status_code == 403

    # Add permission and verify access
    assert as_admin.post('/projects/' + project + '/permissions', json={
        '_id': 'user@user.com',
        'access': 'ro'
    }).ok
    r = as_user.get('/jobs/' + job + '/detail')
    assert r.ok

    # Now delete the acquisition (inputs)
    assert as_admin.delete('/acquisitions/' + acquisition).ok
    r = as_user.get('/jobs/' + job + '/detail')
    assert r.ok
    r_detail = r.json()

    # Endpoint should still work, refs should still exist
    # No object in the output though
    zip_input = r_detail['inputs']['zip']
    assert zip_input['ref']['name'] == 'test.zip'
    assert zip_input['ref']['type'] == 'acquisition'
    assert zip_input['ref']['id'] == acquisition
    assert 'object' not in zip_input

    csv_input = r_detail['inputs']['csv']
    assert csv_input['ref']['name'] == 'test.csv'
    assert csv_input['ref']['type'] == 'acquisition'
    assert csv_input['ref']['id'] == acquisition
    assert 'object' not in csv_input

    # Now delete the session (destination)
    assert as_admin.delete('/sessions/' + session).ok

    # No longer accessible to user
    r = as_user.get('/jobs/' + job + '/detail')
    assert r.status_code == 403

    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok
    r_detail = r.json()

    # Verify parent container info
    assert r_detail['parent_info']['group']['_id'] == group
    assert r_detail['parent_info']['group']['label'] == 'job-detail group'

    assert r_detail['parent_info']['project']['_id'] == project
    assert r_detail['parent_info']['project']['label'] == 'job-detail project'

    assert r_detail['parent_info']['subject']['label'] == 'unknown'

    assert r_detail['parent_info']['session']['_id'] == session
    assert 'label' not in r_detail['parent_info']['session']

    # Verify outputs still have references
    zip_out, csv_out = r_detail['outputs']
    if zip_out['ref']['name'] == 'result.csv':
        zip_out, csv_out = csv_out, zip_out

    assert zip_out['ref']['name'] == 'result.zip'
    assert zip_out['ref']['type'] == 'session'
    assert zip_out['ref']['id'] == session
    assert 'object' not in zip_out

    assert csv_out['ref']['name'] == 'result.csv'
    assert csv_out['ref']['type'] == 'session'
    assert csv_out['ref']['id'] == session
    assert 'object' not in csv_out

    # ===== Mangled job object =====

    # input without ids
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'inputs': [{'input': 'garbage'}]}})
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok

    # None for inputs
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$unset': {'inputs': ''}})
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok

    # Empty inputs
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'inputs': []}})
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok

    # Empty config
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'config': {}}})
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok

    # No destination
    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$unset': {'destination': ''}})
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok

    api_db.jobs.update_one({'_id': bson.ObjectId(job)}, {'$set': {'destination': None}})
    r = as_admin.get('/jobs/' + job + '/detail')
    assert r.ok

def test_failed_rule_execution(data_builder, default_payload, as_user, as_admin, as_drone, api_db, file_form):
    # create gear
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)
    gear2 = data_builder.create_gear()
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip'))
    assert r.ok

    # create invalid rule for the project
    result = api_db.project_rules.insert_one({
        'project_id': project,
        'gear_id': gear2,
        'name': 'text-trigger',
        'any': [],
        'not': [],
        'all': [{'type': 'file.type', 'value': '[[', 'regex': True}]
    })
    rule_id = result.inserted_id

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
    r = as_drone.post('/jobs/' + job + '/prepare-complete')
    assert r.ok

    # verify that job ticket has been created
    job_ticket = api_db.job_tickets.find_one({'job': job})
    assert job_ticket['timestamp']

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

    # Post complete
    r = as_drone.post('/jobs/' + job + '/complete', json={'success': True})
    assert r.ok

    # verify that no job was spawned for uploaded files (Due to error)
    jobs = [j for j in api_db.jobs.find({'gear_id': gear2})]
    assert len(jobs) == 0

    # Verify job logs contains informational message about saved files & failed rules
    expected_job_logs = [
        {'fd': -1, 'msg': 'The following project rules could not be evaluated:\n'},
        {'fd': -1, 'msg': '  - {}: text-trigger\n'.format(rule_id)},
        {'fd': -1, 'msg': 'The following outputs have been saved:\n'},
        {'fd': -1, 'msg': '  - result.txt\n'},
    ]

    r = as_admin.get('/jobs/' + job + '/logs')
    assert r.ok
    assert r.json()['logs'] == expected_job_logs

def test_job_providers(site_providers, data_builder, default_payload, as_public, as_user, as_admin, api_db, file_form):
    gear_name = data_builder.randstr()
    gear_doc = default_payload['gear']['gear']
    gear_doc['name'] = gear_name
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear_id = data_builder.create_gear(gear=gear_doc)
    group = data_builder.create_group(providers={})  # Create group without providers
    project = data_builder.create_project(group=group)
    session = data_builder.create_session(project=project)
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    # Ensure that user is a project admin
    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': user_id
    }).ok

    site_provider = site_providers['compute']
    override_provider = data_builder.create_compute_provider()

    job_data_orig = {
        'gear_id': gear_id,
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

    # === Non-center gear ===
    # Cannot create job
    job_data = copy.deepcopy(job_data_orig)
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 412

    r = as_admin.post('/jobs/determine_provider', json=job_data)
    assert r.status_code == 412

    # Validate overridden provider_id
    job_data['compute_provider_id'] = str(bson.ObjectId())
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 422

    # Cannot override provider_id on job (if not admin)
    job_data['compute_provider_id'] = override_provider
    r = as_user.post('/jobs/add', json=job_data)
    assert r.status_code == 403

    # Can override provider_id on job (if admin)
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id = r.json()['_id']

    # Still return 412 on determine_provider because we ignore overridden provider
    r = as_admin.post('/jobs/determine_provider', json=job_data)
    assert r.status_code == 412

    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == override_provider

    # Retried job should have the original provider id by default
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {'gear-name': [gear_name]},
        'return': {'jobs': 1},
    }))
    assert r.ok
    assert r.json()['jobs'][0]['id'] == job_id

    assert as_admin.put('/jobs/' + job_id, json={'state': 'failed'}).ok

    r = as_admin.post('/jobs/' + job_id + '/retry')
    assert r.ok
    retried_job_id = r.json()['_id']

    r = as_admin.get('/jobs/' + retried_job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == override_provider

    # Override provider on retried job
    r = as_admin.post('/jobs/ask', json=question({
        'whitelist': {'gear-name': [gear_name]},
        'return': {'jobs': 1},
    }))
    assert r.ok
    assert r.json()['jobs'][0]['id'] == retried_job_id
    assert as_admin.put('/jobs/' + retried_job_id, json={'state': 'failed'}).ok

    # Retry validates provider
    r = as_admin.post('/jobs/' + retried_job_id + '/retry', params={'computeProviderId': str(bson.ObjectId())})
    assert r.status_code == 422

    r = as_admin.post('/jobs/' + retried_job_id + '/retry', params={'computeProviderId': site_provider})
    assert r.ok
    retried_job_id2 = r.json()['_id']

    r = as_admin.get('/jobs/' + retried_job_id2)
    assert r.ok
    assert r.json()['compute_provider_id'] == site_provider

    # Cannot create analysis
    job_data = copy.deepcopy(job_data_orig)
    del job_data['destination']
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'online-1',
        'job': job_data
    })
    assert r.status_code == 412

    # Can override provider_id on analysis (if admin)
    job_data['compute_provider_id'] = override_provider
    r = as_user.post('/sessions/' + session + '/analyses', json={
        'label': 'online-2',
        'job': job_data
    })
    assert r.status_code == 403

    # Can override provider_id on job (if admin)
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'online-3',
        'job': job_data
    })
    assert r.ok
    analysis_id = r.json()['_id']

    r = as_admin.get('/analyses/' + analysis_id)
    assert r.ok
    job_id = r.json()['job']

    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == override_provider

    # === Center gear ===
    assert as_admin.put('/site/settings', json={'center_gears': [gear_name]}).ok

    # Cannot create job (no device origin)
    job_data = copy.deepcopy(job_data_orig)
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.status_code == 412

    # Can create job (device origin)
    api_db.acquisitions.update_one({'_id': bson.ObjectId(acquisition)}, {'$set': {'files.0.origin.type': 'device'}})

    # Get site provider back
    r = as_admin.post('/jobs/determine_provider', json=job_data)
    r_provider = r.json()
    for key in ('created', 'modified', 'label', 'origin', 'provider_class', 'provider_type'):
        assert key in r_provider
    assert r_provider['_id'] == site_provider

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id = r.json()['_id']

    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == site_provider

    # Can override provider_id on job (if admin)
    job_data['compute_provider_id'] = override_provider
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id = r.json()['_id']

    r = as_admin.post('/jobs/determine_provider', json=job_data)
    assert r.json()['_id'] == site_provider

    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == override_provider

    # Can create analyses
    job_data = copy.deepcopy(job_data_orig)
    del job_data['destination']
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'online-4',
        'job': job_data
    })
    assert r.ok
    analysis_id = r.json()['_id']

    r = as_admin.get('/analyses/' + analysis_id)
    assert r.ok
    job_id = r.json()['job']

    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == site_provider

    # Can override provider_id on analysis (if admin)
    job_data['compute_provider_id'] = override_provider
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'online-5',
        'job': job_data
    })
    assert r.ok
    analysis_id = r.json()['_id']

    r = as_admin.get('/analyses/' + analysis_id)
    assert r.ok
    job_id = r.json()['job']

    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    assert r.json()['compute_provider_id'] == override_provider
