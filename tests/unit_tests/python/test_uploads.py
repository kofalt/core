import json
import urlparse

from api import config
from mock import MagicMock


def test_signed_url_reaper_upload(as_drone, mocker, api_db, with_site_settings):

    # Upload without signed URLs returns 200 with None as the content
    payload = {
        'metadata': {
            'group': {'_id': 'scitran'},
            'project': {'label': ''},
            'session': {
                'uid': 'session_uid',
                'subject': {'code': 'bela'}
            },
            'acquisition': {
                'uid': 'acquisition_uid',
                'files': [
                    {'name': 'test'},
                    {'name': 'test2'}
                ]
            }
        },
        'filenames': [
            'test',
            'test2'
        ]
    }

    r = as_drone.post('/upload/reaper?ticket=',
                     json=payload)

    # return should be None which is empty content when no signed urls
    assert r.ok
    assert r.content_length == 0

    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    r = as_drone.post('/upload/reaper?ticket=',
                      json=payload)

    assert r.ok
    assert r.json['urls'] == {'test': 'url', 'test2': 'url'}
    assert mock_get_signed.call_count == 2

    ticket_id = r.json['ticket']

    r = as_drone.post('/upload/reaper?ticket=' + ticket_id)
    assert r.ok

    # Cant get to the mock_fs without breaking the constructor
    # TODO: Find a way to spy on this without breaking the object
    # assert mock_fs.move.call_count == 0


def test_signed_url_label_upload(as_drone, data_builder, mocker):
    group = data_builder.create_group()

    payload = {
        'metadata': {
            'group': {'_id': group},
            'project': {
                'label': 'test_project',
                'files': [{'name': 'project.csv'}]
            }
        },
        'filenames': [
            'project.csv'
        ]
    }

    r = as_drone.post('/upload/label?ticket=',
                     json=payload)

    assert r.status_code == 200
    assert r.content_length == 0

    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    r = as_drone.post('/upload/label?ticket=',
                      json=payload)

    assert r.ok
    assert r.json['urls'] == {'project.csv': 'url'}
    assert mock_is_signed.call_count == 1

    ticket_id = r.json['ticket']

    r = as_drone.post('/upload/label?ticket=' + ticket_id)
    assert r.ok

    # assert not mock_fs.move.called


def test_signed_url_engine_upload(as_drone, data_builder, mocker):
    project = data_builder.create_project()

    payload = {
        'metadata': {
            'project': {
                'label': 'engine project',
                'info': {'test': 'p'},
                'files': [
                    {
                        'name': 'one.csv',
                        'type': 'engine type 0',
                        'info': {'test': 'f0'}
                    }
                ]
            }
        },
        'filenames': [
            'one.csv'
        ]
    }

    # upload without signed url should return None
    r = as_drone.post('/engine?upload_ticket=&level=%s&id=%s' % ('project', project),
                     json=payload)

    assert r.status_code == 200
    assert r.content_length == 0

    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    r = as_drone.post('/engine?upload_ticket=&level=%s&id=%s' % ('project', project),
                      json=payload)

    assert r.ok
    assert r.json['urls'] == {'one.csv': 'url'}
    assert mock_get_signed.call_count == 1

    ticket_id = r.json['ticket']

    r = as_drone.post('/engine?upload_ticket=%s&level=%s&id=%s' % (ticket_id, 'project', project))
    assert r.ok

    # assert not mock_fs.move.called


def test_signed_url_analysis_engine_upload(data_builder, file_form, as_drone, mocker):
    session = data_builder.create_session()

    body = file_form(
        'one.csv', meta={'label': 'test analysis', 'inputs': [{'name': 'one.csv'}]}
    )
    # create acquisition analysis
    r = as_drone.post('/sessions/' + session + '/analyses', POST=body)
    assert r.ok
    session_analysis = r.json['_id']

    payload = {
        'metadata': {
            'type': 'text',
            'value': {'label': 'test'},
            'enabled': True
        },
        'filenames': [
            'one.csv'
        ]
    }

    # Non Signed Url upload will return None
    r = as_drone.post('/engine?upload_ticket=&level=%s&id=%s' % ('analysis', session_analysis),
                      json=payload)

    assert r.status_code == 200
    assert r.content_length == 0

    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    r = as_drone.post('/engine?upload_ticket=&level=%s&id=%s' % ('analysis', session_analysis),
                      json=payload)

    assert r.ok
    assert r.json['urls'] == {'one.csv': 'url'}
    assert mock_is_signed.call_count == 1

    ticket_id = r.json['ticket']

    r = as_drone.post('/engine?upload_ticket=%s&level=%s&id=%s' % (ticket_id, 'analysis', session_analysis))
    assert r.ok

    # assert not mock_fs.move.called

    # delete acquisition analysis
    r = as_drone.delete('/sessions/' + session + '/analyses/' + session_analysis)
    assert r.ok

def test_signed_url_filelisthandler_upload(as_drone, data_builder, mocker):
    project = data_builder.create_project()

    payload = {
        'metadata': {},
        'filenames': [
            'one.csv'
        ]
    }

    r = as_drone.post('/projects/' + project + '/files?ticket=', json=payload)

    assert  r.ok
    assert r.content_length == 0

    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})
    r = as_drone.post('/projects/' + project + '/files?ticket=', json=payload)


    assert r.ok
    assert r.json['urls'] == {'one.csv': 'url'}
    assert mock_get_signed.call_count == 1

    ticket_id = r.json['ticket']

    r = as_drone.post('/projects/' + project + '/files?ticket=' + ticket_id)
    assert r.ok

def test_upload_with_virus_scan_enabled(mocker, as_public, as_user, as_drone, as_admin, data_builder, file_form, api_db):
    # setup
    mock_get_feature = mocker.patch('api.placer.config.get_feature', return_value={'virus_scan': True})
    mock_config = config.get_config()
    mock_config['webhooks']['virus_scan'] = None
    mock_get_feature = mocker.patch('api.placer.config.get_config', return_value=mock_config)
    mock_webhook_post = mocker.patch('api.webhooks.base.Session.post')
    orig_find = config.db['acquisitions'].find
    def wrap_find(*args, **kwargs):
        return orig_find(args[0])
    mocker.patch.object(config.db['acquisitions'], 'find', wraps=wrap_find)
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition(session=session)

    gear_config = {'param': {'type': 'string', 'pattern': '^default|custom$', 'default': 'default'}}
    gear = data_builder.create_gear(gear={'version': '0.0.1', 'config': gear_config})

    # create rule
    rule_json = {
        'gear_id': gear,
        'name': 'csv-job-trigger-rule',
        'any': [],
        'not': [],
        'all': [
            {'type': 'file.type', 'value': 'tabular data'},
        ]
    }

    r = as_admin.post('/projects/' + project + '/rules', json=rule_json)
    assert r.ok
    rule = r.json['_id']

    # upload file as drone
    file_name = 'test.csv'
    r = as_drone.post('/acquisitions/' + acquisition + '/files', POST=file_form(file_name))
    assert r.ok
    # job was created via rule since the file was uploaded by a trusted origin
    gear_jobs = [job for job in api_db.jobs.find({'gear_id': gear})]
    assert len(gear_jobs) == 1
    # file uploaded by drone won't be quarantined
    r = as_drone.get('/acquisitions/' + acquisition + '/files/test.csv')
    assert r.ok

    uid = as_user.get('/users/self').json['_id']
    r = as_drone.post('/projects/' + project + '/permissions', json={'_id': uid, 'access': 'admin'})
    assert r.ok

    # user uploads fails if not webhook configure
    r = as_user.post('/acquisitions/' + acquisition + '/files', POST=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))
    assert not r.ok
    assert r.status_code == 500

    # set webhook
    mock_config['webhooks']['virus_scan'] = 'http://localhost'
    mock_get_feature.return_value = mock_config

    # upload file as user
    r = as_user.post('/acquisitions/' + acquisition + '/files', POST=file_form((file_name, 'some;content')))
    assert r.ok

    # job was not created via rule since the file is quarantined
    gear_jobs = [job for job in api_db.jobs.find({'gear_id': gear})]
    assert len(gear_jobs) == 1

    # user uploaded file is quarantined
    r = as_user.get('/acquisitions/' + acquisition + '/files/test.csv')
    assert not r.ok
    assert r.status_code == 400

    _, kwargs = mock_webhook_post.call_args_list[0]
    webhook_payload = json.loads(kwargs['data'])
    # can download the file using the signed url
    parsed_url = urlparse.urlparse(webhook_payload['file_download_url'])
    download_endpoint = parsed_url.path.replace('/api', '')
    r = as_public.get('{}?{}'.format(download_endpoint, parsed_url.query))
    assert r.ok
    assert r.body == 'some;content'
    # can use the signed response url to send back the virus scan result
    parsed_url = urlparse.urlparse(webhook_payload['response_url'])
    response_endpoint = parsed_url.path.replace('/api', '')
    # mark the file as clean using
    r = as_public.post('{}?{}'.format(response_endpoint, parsed_url.query), json={'state': 'clean'})
    assert r.ok

    # now the file is accessible
    r = as_user.get('/acquisitions/' + acquisition + '/files/test.csv')
    assert r.ok

    # job was created via rule since the file is marked as clean
    gear_jobs = [job for job in api_db.jobs.find({'gear_id': gear})]
    assert len(gear_jobs) == 2
