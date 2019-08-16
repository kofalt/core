import datetime
import os
import sys
import json
import bson
from bson.objectid import ObjectId
import pytest

from api import config, util
from api.site.providers.repository import get_provider


@pytest.fixture(scope='function')
def cleanup_deleted(mocker, monkeypatch, with_site_settings):
    """Enable importing from `bin` and return `cleanup_deleted`."""
    monkeypatch.setenv('SCITRAN_PERSISTENT_FS_URL', config.__config['persistent']['fs_url'])

    bin_path = os.path.join(os.getcwd(), 'bin')
    mocker.patch('sys.path', [bin_path] + sys.path)
    import cleanup_deleted
    return cleanup_deleted


def test_cleanup_deleted_files(data_builder, randstr, file_form, as_admin, api_db, cleanup_deleted, with_site_settings):
    """
    This tests that tickets (which allow downloading a file) get deleted
    after 72 hours and not before.
    """
    session_id = data_builder.create_session()
    session = as_admin.get('/sessions/' + session_id)
    project_id = json.loads(session.content)['parents']['project']
    project = as_admin.get('/projects/' + project_id)
    storage_provider = get_provider(
        json.loads(project.content)['providers']['storage'])

    file_name_1 = '%s.csv' % randstr()
    file_content_1 = randstr()
    as_admin.post('/sessions/' + session_id + '/files',
                  files=file_form((file_name_1, file_content_1)))

    # get the ticket
    r = as_admin.get('/sessions/' + session_id + '/files/' + file_name_1,
                     params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download the file
    assert as_admin.get('/sessions/' + session_id + '/files/' + file_name_1,
                        params={'ticket': ticket}).ok

    # Test that the file won't be deleted if it was deleted in the last 72 hours
    d = datetime.datetime.now() - datetime.timedelta(hours=70)

    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.deleted': d}}
    )

    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_1}
    )['files'][0]
    file_id_1 = file_info['_id']

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')
    assert storage_provider.storage_plugin.get_file_info(
        file_id_1, util.path_from_uuid(file_id_1)) is not None

    # file won't be deleted after 72 hours if the origin is a user
    d = datetime.datetime.now() - datetime.timedelta(hours=73)

    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.deleted': d}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')
    assert storage_provider.storage_plugin.get_file_info(
        file_id_1, util.path_from_uuid(file_id_1)) is not None

    # file deleted after 72 hours if the origin is not a user
    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.origin.type': 'device'}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    # file removed from the filesystem
    assert storage_provider.storage_plugin.get_file_info(
        file_id_1, util.path_from_uuid(file_id_1)) is None

    # file also removed from the database
    document = api_db['sessions'].find_one(
        {'files.name': file_name_1}
    )

    assert document is None

    # check when the parent container is deleted
    session_id_2 = data_builder.create_session()

    file_name_2 = '%s.csv' % randstr()
    file_content_2 = randstr()
    as_admin.post('/sessions/' + session_id_2 + '/files', files=file_form((file_name_2, file_content_2)))

    file_name_3 = '%s.csv' % randstr()
    file_content_3 = randstr()
    as_admin.post('/sessions/' + session_id_2 + '/files', files=file_form((file_name_3, file_content_3)))

    # Test that the file won't be deleted if it was deleted in the last 72 hours
    d = datetime.datetime.now() - datetime.timedelta(hours=70)

    # Mark session as deleted
    api_db['sessions'].find_one_and_update(
        {'_id': ObjectId(session_id_2)},
        {'$set': {'deleted': d}}
    )

    # Upload two test file
    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_2}
    )['files'][0]
    file_id_2 = file_info['_id']

    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_3}
    )['files'][1]
    file_id_3 = file_info['_id']

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    # files still exist
    assert storage_provider.storage_plugin.get_file_info(
        file_id_2, util.path_from_uuid(file_id_2)) is not None
    assert storage_provider.storage_plugin.get_file_info(
        file_id_3, util.path_from_uuid(file_id_3)) is not None

    # file won't be deleted after 72 hours if the origin is a user
    d = datetime.datetime.now() - datetime.timedelta(hours=73)

    api_db['sessions'].find_one_and_update(
        {'_id': ObjectId(session_id_2)},
        {'$set': {'deleted': d}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    assert storage_provider.storage_plugin.get_file_info(
        file_id_2, util.path_from_uuid(file_id_2)) is not None
    assert storage_provider.storage_plugin.get_file_info(
        file_id_3, util.path_from_uuid(file_id_3)) is not None

    # file deleted after 72 hours if the origin is not a user
    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_2},
        {'$set': {'files.$.origin.type': 'device'}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    # first file removed from the filesystem
    assert storage_provider.storage_plugin.get_file_info(
        file_id_2, util.path_from_uuid(file_id_2)) is None
    # but the second file is still there
    assert storage_provider.storage_plugin.get_file_info(
        file_id_3, util.path_from_uuid(file_id_3)) is not None

    # upload a file into the first session to see that it is kept when we use the --all flag
    # but others which are marked to delete will be removed
    file_name_4 = '%s.csv' % randstr()
    file_content_4 = randstr()
    as_admin.post(
        '/sessions/' + session_id + '/files',
        files=file_form((file_name_4, file_content_4))
    )

    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_4}
    )['files'][0]
    file_id_4 = file_info['_id']

    # with --all flag we delete every files which are marked to delete
    # don't care about the origin
    cleanup_deleted.main('--log-level', 'DEBUG', '--all')
    assert storage_provider.storage_plugin.get_file_info(
        file_id_3, util.path_from_uuid(file_id_3)) is None
    # we keep files which are not marked
    assert storage_provider.storage_plugin.get_file_info(
        file_id_4, util.path_from_uuid(file_id_4)) is not None

    # Mark the first session as deleted
    api_db['sessions'].find_one_and_update(
        {'_id': ObjectId(session_id)},
        {'$set': {'deleted': d}}
    )

    # now the fourth file will be deleted too
    cleanup_deleted.main('--log-level', 'DEBUG', '--all')
    assert storage_provider.storage_plugin.get_file_info(
        file_id_4, util.path_from_uuid(file_id_4)) is None


def test_cleanup_single_project(data_builder, default_payload, randstr, file_form, as_admin, as_drone, api_db, cleanup_deleted, with_site_settings, site_gear):
    # Some tests are leaving partial jobs in the db that kill the tests
    # This is a quick and dirty way to get to a clean state without filtering 
    api_db.jobs.remove({})

    acquisition_id = data_builder.create_acquisition()
    acquisition = as_admin.get('/acquisitions/' + acquisition_id)
    session_id = json.loads(acquisition.content)['parents']['session']
    session = as_admin.get('/sessions/' + session_id)
    project_id = json.loads(session.content)['parents']['project']
    project = as_admin.get('/projects/' + project_id)
    storage_provider = get_provider(
        json.loads(project.content)['providers']['storage'])

    file_name_1 = '%s.csv' % randstr()
    file_content_1 = randstr()
    as_admin.post('/sessions/' + session_id + '/files', files=file_form((file_name_1, file_content_1)))

    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_1}
    )['files'][0]
    file_id_1 = file_info['_id']

    # Create ad-hoc analysis
    r = as_admin.post('/sessions/' + session_id + '/analyses', json={
        'label': 'offline',
        'inputs': [{'type': 'session', 'id': session_id, 'name': file_name_1}]
    })
    assert r.ok

    # get the ticket
    r = as_admin.get('/sessions/' + session_id + '/files/' + file_name_1, params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download the file
    assert as_admin.get('/sessions/' + session_id + '/files/' + file_name_1, params={'ticket': ticket}).ok

    # run a job
    api_db.gears.update({'_id': bson.ObjectId(site_gear)}, {'$set': {'gear.inputs': {'dicom': {'base': 'file'}}}})
    gear = site_gear

    job_data = {
        'gear_id': gear,
        'inputs': {
            'dicom': {
                'type': 'session',
                'id': session_id,
                'name': file_name_1
            }
        },
        'config': { 'two-digit multiple of ten': 20 },
        'destination': {
            'type': 'acquisition',
            'id': acquisition_id
        },
        'tags': [ 'test-tag' ]
    }
    # add job with explicit destination
    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id = r.json()['_id']

    # start job (Adds logs)
    r = as_admin.get('/jobs/next')
    assert r.ok

    # prepare completion (send success status before engine upload)
    r = as_drone.post('/jobs/' + job_id + '/prepare-complete')
    assert r.ok

    # verify that job ticket has been created
    job_ticket = api_db.job_tickets.find_one({'job': job_id})
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
        params={'level': 'acquisition', 'id': acquisition_id, 'job': job_id, 'job_ticket': job_ticket['_id']},
        files=file_form('result.txt', meta=produced_metadata)
    )
    assert r.ok

    # Make sure produced metadata and logs exist
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    job = r.json()
    assert job.get('produced_metadata')

    r = as_admin.get('/jobs/' + job_id + '/logs')
    assert r.ok
    assert r.json().get('logs')

    # Try cleaning undeleted project
    cleanup_deleted.main('--log-level', 'DEBUG', '--all', '--project', project_id, '--job-phi')

    # Make sure file is still there
    assert storage_provider.storage_plugin.get_file_info(
        file_id_1, util.path_from_uuid(file_id_1))

    # Make sure job phi is still there
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    job = r.json()
    assert job.get('produced_metadata')

    r = as_admin.get('/jobs/' + job_id + '/logs')
    assert r.ok
    assert r.json().get('logs')

    # delete the project
    r = as_admin.delete('/projects/' + project_id)
    assert r.ok

    # Run cleanup again
    cleanup_deleted.main('--log-level', 'DEBUG', '--all', '--project', project_id, '--job-phi')

    # Make sure file is not there
    assert not storage_provider.storage_plugin.get_file_info(
        file_id_1, util.path_from_uuid(file_id_1))

    # Check job phi
    r = as_admin.get('/jobs/' + job_id)
    assert r.ok
    job = r.json()
    assert not job.get('produced_metadata')

    r = as_admin.get('/jobs/' + job_id + '/logs')
    assert r.ok
    assert not r.json().get('logs')

    assert not api_db.projects.find_one({'_id': ObjectId(project_id)})
    assert not api_db.subjects.find_one({'parents.project': ObjectId(project_id)})
    assert not api_db.sessions.find_one({'parents.project': ObjectId(project_id)})
    assert not api_db.acquisitions.find_one({'parents.project': ObjectId(project_id)})
    assert not api_db.analyses.find_one({'parents.project': ObjectId(project_id)})
