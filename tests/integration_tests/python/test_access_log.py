import time
import bson
import pytest

from api.web.request import AccessType

from api.access_log import create_entry, bulk_log_access

class MockRequest:
    def __init__(self, method, path):
        self.method = method
        self.path = path
        self.client_addr = '127.0.0.1'


# NOTE these tests assume they are not running in parallel w/ other tests
# by relying on the last entry in the logs

def test_access_log_succeeds(data_builder, as_admin, log_db, with_site_settings):
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    file_name = 'one.csv'

    ###
    # Test login action is logged
    ###

    api_key = as_admin.get('/users/self').json()['api_key']['key']

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.post('/login', json={
        'auth_type': 'api-key',
        'code': api_key
    })
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]
    assert most_recent_log['access_type'] == AccessType.user_login.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test logout action is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.post('/logout')
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]
    assert most_recent_log['access_type'] == AccessType.user_logout.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test project access is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/projects/' + project)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['access_type'] == AccessType.view_container.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test session access is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/sessions/' + session)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['session']['id'] == session
    assert most_recent_log['access_type'] == AccessType.view_container.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test acquisition access is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['acquisition']['id'] == acquisition
    assert most_recent_log['access_type'] == AccessType.view_container.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Add subject info
    ###

    subject_code = 'Test subject code'
    r = as_admin.put('/sessions/' + session, json={
        'subject': {'code': subject_code}}
    )
    assert r.ok


    ###
    # Test subject access is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/sessions/' + session + '/subject')
    assert r.ok
    subject = r.json()['_id']

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['session']['id'] == session
    assert most_recent_log['context']['subject']['label'] == subject_code
    assert most_recent_log['access_type'] == AccessType.view_subject.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test subject access is logged on new subject route
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/subjects/' + subject)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['subject']['label'] == subject_code
    assert most_recent_log['access_type'] == AccessType.view_subject.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    # Upload files
    r = as_admin.post('/projects/' + project + '/files', files={
        'file': (file_name, 'test-content')
    })
    assert r.ok


    ###
    # Test file download is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/projects/' + project + '/files/' + file_name)
    assert r.ok

    file_ = r.raw.read(10)
    time.sleep(1)

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['context']['file']['name'] == file_name
    assert most_recent_log['access_type'] == AccessType.download_file.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test file ticket download is logged once
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/projects/' + project + '/files/' + file_name, params={'ticket': ''})
    assert r.ok

    ticket_id = r.json()['ticket']

    r = as_admin.get('/projects/' + project + '/files/' + file_name, params={'ticket': ticket_id})
    assert r.ok

    file_ = r.raw.read(10)
    time.sleep(1)

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['context']['file']['name'] == file_name
    assert most_recent_log['context']['ticket_id'] == ticket_id
    assert most_recent_log['access_type'] == AccessType.download_file.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    # Upload another file
    r = as_admin.post('/sessions/' + session + '/files', files={
        'file': (file_name, 'test-content')
    })
    assert r.ok


    ###
    # Test container bulk download
    ###

    log_records_count_before = log_db.access_log.count({})
    r = as_admin.post('/download', json={'optional': True, 'nodes':[{'level': 'project', '_id': project}]})
    assert r.ok
    ticket_id = r.json()['ticket']
    file_count = r.json()['file_cnt']
    r = as_admin.get('/download', params={'ticket':ticket_id})
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before + file_count == log_records_count_after

    most_recent_logs = log_db.access_log.find({}).sort([('_id', -1)]).limit(file_count)
    for l in most_recent_logs:
        assert l['context']['file']['name'] == file_name
        assert l['access_type'] == AccessType.download_file.value
        assert l['origin']['id'] == 'admin@user.com'

    ###
    # Test search bulk download
    ###

    log_records_count_before = log_db.access_log.count({})
    r = as_admin.post('/download', params={'bulk':True},
                      json={"files":[{"container_name":"project","container_id":project,"filename":file_name},
                                     {"container_name":"session","container_id":session,"filename":file_name}]})
    assert r.ok
    ticket_id = r.json()['ticket']
    file_count = r.json()['file_cnt']
    r = as_admin.get('/download', params={'ticket':ticket_id})
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before + file_count == log_records_count_after

    most_recent_logs = log_db.access_log.find({}).sort([('_id', -1)]).limit(file_count)
    for l in most_recent_logs:
        assert l['context']['file']['name'] == file_name
        assert l['access_type'] == AccessType.download_file.value
        assert l['origin']['id'] == 'admin@user.com'


    ###
    # Test file info access is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.get('/projects/' + project + '/files/' + file_name + '/info')
    assert r.ok
    assert r.json()['name'] == file_name

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['context']['file']['name'] == file_name
    assert most_recent_log['access_type'] == AccessType.view_file.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test file replacement is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    # Replace existing file
    r = as_admin.post('/projects/' + project + '/files', files={
        'file': (file_name, 'different-content')
    })
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['context']['file']['name'] == file_name
    assert most_recent_log['access_type'] == AccessType.replace_file.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test file delete is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.delete('/projects/' + project + '/files/' + file_name)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['context']['file']['name'] == file_name
    assert most_recent_log['access_type'] == AccessType.delete_file.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test acquisition delete is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.delete('/acquisitions/' + acquisition)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['acquisition']['id'] == acquisition
    assert most_recent_log['access_type'] == AccessType.delete_container.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test session delete is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.delete('/sessions/' + session)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['session']['id'] == session
    assert most_recent_log['access_type'] == AccessType.delete_container.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'


    ###
    # Test project delete is logged
    ###

    log_records_count_before = log_db.access_log.count({})

    r = as_admin.delete('/projects/' + project)
    assert r.ok

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+1 == log_records_count_after

    most_recent_log = log_db.access_log.find({}).sort([('_id', -1)]).limit(1)[0]

    assert most_recent_log['context']['project']['id'] == project
    assert most_recent_log['access_type'] == AccessType.delete_container.value
    assert most_recent_log['origin']['id'] == 'admin@user.com'



def test_access_log_fails(data_builder, as_admin, log_db):
    project = data_builder.create_project()
    file_name = 'one.csv'

    log_db.command('collMod', 'access_log', validator={'$and': [{'foo': {'$exists': True}}]}, validationLevel='strict')

    # Upload files
    r = as_admin.post('/projects/' + project + '/files', files={
        'file': (file_name, 'test-content')
    })
    assert r.ok

    ###
    # Test file delete request fails and does not delete file
    ###

    r = as_admin.delete('/projects/' + project + '/files/' + file_name)
    assert r.status_code == 500

    log_db.command('collMod', 'access_log', validator={}, validationLevel='strict')

    r = as_admin.get('/projects/' + project)
    assert r.ok
    assert r.json()['files']

def test_create_entry_validation():
    # Could be a unit test?
    req = MockRequest('GET', '/test')
    origin = { 'type': 'user', 'id': 'admin@user.com' }

    try:
        # Invalid access type
        create_entry(req, 'view_subject', origin, { 'group': { 'id': 'test' } })
        pytest.fail('Expected exception!')
    except Exception:
        pass

    try:
        # Missing context
        create_entry(req, AccessType.view_subject, origin, context=None)
        pytest.fail('Expected exception!')
    except Exception:
        pass

    try:
        # Missing file entry
        create_entry(req, AccessType.view_file, origin, context={ 'group': { 'id': 'test' }})
        pytest.fail('Expected exception!')
    except Exception:
        pass

    #Valid
    create_entry(req, AccessType.view_file, origin, context={ 'group': { 'id': 'test' }, 'file': {'name': 'test.txt'} })


def test_bulk_access(data_builder, as_admin, log_db):
    project = data_builder.create_project(label='Test Project')

    log_records_count_before = log_db.access_log.count({})

    req = MockRequest('GET', '/test/bulk_log_access')
    origin = { 'type': 'user', 'id': 'admin@user.com' }

    entries = [
        (AccessType.view_container, {
            'group': { 'id': 'test', 'label': 'Test Group' }
        }),
        (AccessType.view_file, {
            'group': { 'id': 'test', 'label': 'Test Group' },
            'project': { 'id': project, 'label': 'Test Project' },
            'file': { 'name': 'example.csv' }
        })
    ]

    bulk_log_access(req, origin, entries)

    log_records_count_after = log_db.access_log.count({})
    assert log_records_count_before+2 == log_records_count_after

    most_recent_logs = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(2)

    from pprint import pprint
    pprint(most_recent_logs)
    if most_recent_logs[0]['access_type'] == 'view_file':
        log1 = most_recent_logs[1]
        log2 = most_recent_logs[0]
    else:
        log1 = most_recent_logs[0]
        log2 = most_recent_logs[1]

    assert log1['access_type'] == AccessType.view_container.value
    assert log1['origin']['id'] == 'admin@user.com'
    assert log1['request_method'] == 'GET'
    assert log1['request_path'] == '/test/bulk_log_access'
    assert log1['context']['group']['id'] == 'test'

    assert log2['access_type'] == AccessType.view_file.value
    assert log2['origin']['id'] == 'admin@user.com'
    assert log2['request_method'] == 'GET'
    assert log2['request_path'] == '/test/bulk_log_access'
    assert log2['context']['file']['name'] == 'example.csv'

def test_job_access(data_builder, as_admin, as_drone, log_db, default_payload,
                    file_form, api_db, with_site_settings):

    from pprint import pprint

    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    project = data_builder.create_project()
    # Projects must have a provider for gear uploads to work 
    update = {'providers': {'storage': 'deadbeefdeadbeefdeadbeef'}}
    r = as_admin.put('/projects/' + project, json=update)
    assert r.ok

    session = data_builder.create_session(project=project)
    subject = str(api_db.subjects.find_one({'project': bson.ObjectId(project)})['_id'])
    acquisition = data_builder.create_acquisition(session=session)
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.zip')).ok

    # Add info to file
    r = as_admin.post('/acquisitions/' + acquisition + '/files/test.zip/info', json={
        'replace': {'a': 'b'}
    })
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition + '/files/test.zip/info')
    assert r.ok
    assert r.json()['info']['a'] == 'b'

    # Add a second file for the analysis
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('analysis-test.zip')).ok
    r = as_admin.post('/acquisitions/' + acquisition + '/files/analysis-test.zip/info', json={
        'replace': {'a': 'b'}
    })
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition + '/files/analysis-test.zip/info')
    assert r.ok
    assert r.json()['info']['a'] == 'b'

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
    job_id = r.json()['_id']

    # get job
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok

    most_recent_logs = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(2)
    pprint(most_recent_logs)
    if most_recent_logs[0]['access_type'] == 'view_file':
        input_log = most_recent_logs[0]
        job_log = most_recent_logs[1]
    else:
        input_log = most_recent_logs[1]
        job_log = most_recent_logs[0]

    assert input_log['access_type'] == AccessType.view_file.value
    assert input_log['origin']['id'] == 'admin@user.com'
    assert input_log['request_method'] == 'GET'
    assert input_log['context']['file']['name'] == 'test.zip'

    assert job_log['access_type'] == AccessType.view_job.value
    assert job_log['origin']['id'] == 'admin@user.com'
    assert job_log['request_method'] == 'GET'
    assert job_log['context']['job']['id'] == job_id

    r = as_drone.get('/jobs/next')
    assert r.ok

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job_id + '/prepare-complete')
    assert r.ok

    # verify that job ticket has been created
    job_ticket = api_db.job_tickets.find_one({'job': job_id})

    # upload metadata
    produced_metadata = {
        'session': {
            'label': 'engine session',
            'subject': {'sex': 'male', 'age': 86400},
            'info': {'test': 's'}
        }
    }

    # engine upload
    r = as_drone.post('/engine',
        params={
            'level': 'acquisition',
            'id': acquisition, 'job': job_id,
            'job_ticket': job_ticket['_id']
        },
        files=file_form(meta=produced_metadata)
    )
    assert r.ok

    # Post complete
    r = as_drone.post('/jobs/' + job_id + '/complete', json={
        'success': True,
        'profile': {
            'elapsed_time_ms': 36501,
            'preparation_time_ms': 2515,
            'upload_time_ms': 1017
        }
    })
    assert r.ok

    # Get the job
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    job = r.json()

    # Verify that produced metadata is preserved
    assert job['produced_metadata'] == produced_metadata

    # Verify that info on config.input.dicom exists
    assert job['config']['inputs']['dicom']['object']['info']['a'] == 'b'

    # Confirm that we logged the produced_metadata view subject and vie container for the
    # produced_metadata
    most_recent_logs = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(4)
    pprint(most_recent_logs)

    logs_tested = 0
    for log in most_recent_logs:
        if log['access_type'] == 'view_subject':
            logs_tested += 1
            assert log['context']['subject']['id'] == subject
            assert log['origin']['id'] == 'admin@user.com'
        if log['access_type'] == 'view_container':
            logs_tested += 1
            assert log['context']['subject']['id'] == subject
            assert log['context']['session']['id'] == session
            assert not log['context'].get('acquisition')
    assert logs_tested == 2

    # Check number of logs
    log_count = log_db.access_log.find({}).count()

    # Verify that produced metadata and info don't appear on a list endpoint
    r = as_admin.get('/jobs', params={'filter': '_id={}'.format(job_id)})
    assert r.ok
    assert r.json()[0].get('produced_metadata') is None
    assert r.json()[0]['config']['inputs']['dicom']['object'].get('info') is None

    # Make sure number of logs is the same
    assert log_count == log_db.access_log.find({}).count()

    # Verify that produced metadata and info don't appear on a list endpoint
    r = as_admin.get('/sessions/' + session + '/jobs',
                     params={'filter': '_id={}'.format(job_id)})
    assert r.ok
    assert not r.json()['jobs'][0].get('produced_metadata')
    assert not r.json()['jobs'][0]['config']['inputs']['dicom']['object'].get('info')

    # Make sure number of logs is the same
    assert log_count == log_db.access_log.find({}).count()
    # Access the logs for the job
    r = as_admin.get('/jobs/' + job_id + '/logs')
    assert r.ok

    # Check number of logs
    assert log_count + 1 == log_db.access_log.find({}).count()
    log_count = log_db.access_log.find({}).count()

    most_recent_log = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(1)[0]
    assert most_recent_log['access_type'] == 'view_job_logs'
    assert most_recent_log['context']['job']['id'] == job_id
    assert most_recent_log['origin']['id'] == 'admin@user.com'

    # Access the logs for the job as text
    r = as_admin.get('/jobs/' + job_id + '/logs/text')
    assert r.ok

    # Check number of logs
    assert log_count + 1 == log_db.access_log.find({}).count()
    log_count = log_db.access_log.find({}).count()

    most_recent_log = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(1)[0]
    assert most_recent_log['access_type'] == 'view_job_logs'
    assert most_recent_log['context']['job']['id'] == job_id
    assert most_recent_log['origin']['id'] == 'admin@user.com'

    # Access the logs for the job as html
    r = as_admin.get('/jobs/' + job_id + '/logs/html')
    assert r.ok

    # Check number of logs
    assert log_count + 1 == log_db.access_log.find({}).count()
    log_count = log_db.access_log.find({}).count()

    most_recent_log = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(1)[0]
    assert most_recent_log['access_type'] == 'view_job_logs'
    assert most_recent_log['context']['job']['id'] == job_id
    assert most_recent_log['origin']['id'] == 'admin@user.com'

    # Unset config
    api_db.jobs.update_one({'_id': bson.ObjectId(job_id)}, {'$unset': {'config': ''}})

    # Verify that produced metadata and info don't appear on a list endpoint
    r = as_admin.get('/jobs', params={'filter': '_id={}'.format(job_id)})
    assert r.ok

    # get job
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok

    # get job detail
    r = as_admin.get('/jobs/' + job_id + '/detail')
    assert r.ok

    # Create analysis job at project level
    r = as_admin.post('/projects/' + project + '/analyses', json={
        'label': 'online',
        'job': {
            'gear_id': gear,
            'inputs': {
                'dicom': {
                    'type': 'acquisition',
                    'id': acquisition,
                    'name': 'analysis-test.zip'
                }
            },
        }
    })
    assert r.ok
    analysis = r.json()['_id']

    # Get log count
    log_count = log_db.access_log.find({}).count()

    # Get the analysis with the job inflated
    r = as_admin.get('/analyses/' + analysis + '?inflate_job=true')
    assert r.ok
    assert 'id' in r.json().get('job', {})

    # Check number of logs
    assert log_count + 3 == log_db.access_log.find({}).count()
    log_count = log_db.access_log.find({}).count()

    most_recent_logs = log_db.access_log.find({}).sort([('timestamp', -1)]).limit(3)
    assert 'view_job' in [log['access_type'] for log in most_recent_logs]

    # Verify ?inflate_jobs=true works for multiple analyses
    r = as_admin.get('/projects/' + project + '/analyses?inflate_job=true')
    assert r.ok
    job = r.json()[0]['job']

    # Check number of logs has not changed
    assert log_count == log_db.access_log.find({}).count()

    assert not job.get('produced_metadata')
    assert not job['config']['inputs']['dicom']['object'].get('info')

    # Delete the input file
    r = as_admin.delete('/acquisitions/' + acquisition + '/files/test.zip')
    assert r.ok

    # Get the job
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok

    # Delete the input file from the db as though it was cleaned up
    api_db.acquisitions.update_one(
        {'_id': bson.ObjectId(acquisition)},
        {'$pull': {'files': {'name': 'test.zip'}}}
    )

    # Get the job
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok


    # The the job access when the group is removed
    r = as_admin.get('/projects/' + project)
    assert r.ok
    group = r.json()['parents']['group']
    r = as_admin.delete('/projects/' + project)
    assert r.ok
    r = as_admin.delete('/groups/' + group)
    assert r.ok   
    r = as_admin.get('/jobs/' + job_id + '/detail')
    assert r.ok
