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

    assert  r.status_code == 405

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

    #We dont have a move interface anymore
    # assert not mock_move.called
