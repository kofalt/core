import datetime
import os
import sys

import pytest

from api import config, util


@pytest.fixture(scope='function')
def cleanup_deleted(mocker, monkeypatch):
    """Enable importing from `bin` and return `cleanup_deleted`."""
    monkeypatch.setenv('SCITRAN_PERSISTENT_FS_URL', config.__config['persistent']['fs_url'])

    bin_path = os.path.join(os.getcwd(), 'bin')
    mocker.patch('sys.path', [bin_path] + sys.path)
    import cleanup_deleted
    return cleanup_deleted


def test_cleanup_deleted_files(data_builder, randstr, file_form, as_admin, api_db, cleanup_deleted):
    session_id = data_builder.create_session()

    file_name_1 = '%s.csv' % randstr()
    file_content_1 = randstr()
    as_admin.post('/sessions/' + session_id + '/files', files=file_form((file_name_1, file_content_1)))

    # get the ticket
    r = as_admin.get('/sessions/' + session_id + '/files/' + file_name_1, params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download the file
    assert as_admin.get('/sessions/' + session_id + '/files/' + file_name_1, params={'ticket': ticket}).ok

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

    cleanup_deleted.main('--log-level', 'DEBUG')

    assert config.fs.exists(util.path_from_uuid(file_id_1))

    # file won't be deleted after 72 hours if the origin is a user
    d = datetime.datetime.now() - datetime.timedelta(hours=73)

    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.deleted': d}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG')

    assert config.fs.exists(util.path_from_uuid(file_id_1))

    # file deleted after 72 hours if the origin is not a user
    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.origin.type': 'device'}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG')

    # file removed from the filesystem
    assert not config.fs.exists(util.path_from_uuid(file_id_1))

    # file also removed from the database
    document = api_db['sessions'].find_one(
        {'files.name': file_name_1}
    )

    assert document is None

