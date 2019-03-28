import datetime
import os
import sys

from bson.objectid import ObjectId
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

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    assert config.primary_storage.get_file_info(file_id_1, util.path_from_uuid(file_id_1)) is not None

    # file won't be deleted after 72 hours if the origin is a user
    d = datetime.datetime.now() - datetime.timedelta(hours=73)

    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.deleted': d}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    assert config.primary_storage.get_file_info(file_id_1, util.path_from_uuid(file_id_1)) is not None

    # file deleted after 72 hours if the origin is not a user
    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_1},
        {'$set': {'files.$.origin.type': 'device'}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    # file removed from the filesystem
    assert config.primary_storage.get_file_info(file_id_1, util.path_from_uuid(file_id_1)) is None

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
    assert config.primary_storage.get_file_info(file_id_2, util.path_from_uuid(file_id_2)) is not None
    assert config.primary_storage.get_file_info(file_id_3, util.path_from_uuid(file_id_3)) is not None

    # file won't be deleted after 72 hours if the origin is a user
    d = datetime.datetime.now() - datetime.timedelta(hours=73)

    api_db['sessions'].find_one_and_update(
        {'_id': ObjectId(session_id_2)},
        {'$set': {'deleted': d}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    assert config.primary_storage.get_file_info(file_id_2, util.path_from_uuid(file_id_2)) is not None
    assert config.primary_storage.get_file_info(file_id_3, util.path_from_uuid(file_id_3)) is not None

    # file deleted after 72 hours if the origin is not a user
    api_db['sessions'].find_one_and_update(
        {'files.name': file_name_2},
        {'$set': {'files.$.origin.type': 'device'}}
    )

    cleanup_deleted.main('--log-level', 'DEBUG', '--reaper')

    # first file removed from the filesystem
    assert config.primary_storage.get_file_info(file_id_2, util.path_from_uuid(file_id_2)) is None
    # but the second file is still there
    assert config.primary_storage.get_file_info(file_id_3, util.path_from_uuid(file_id_3)) is not None

    # upload a file into the first session to see that it is kept when we use the --all flag
    # but others which are marked to delete will be removed
    file_name_4 = '%s.csv' % randstr()
    file_content_4 = randstr()
    as_admin.post('/sessions/' + session_id + '/files', files=file_form((file_name_4, file_content_4)))

    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_4}
    )['files'][0]
    file_id_4 = file_info['_id']

    # with --all flag we delete every files which are marked to delete
    # don't care about the origin
    cleanup_deleted.main('--log-level', 'DEBUG', '--all')
    assert config.primary_storage.get_file_info(file_id_3, util.path_from_uuid(file_id_3)) is None
    # we keep files which are not marked
    assert config.primary_storage.get_file_info(file_id_4, util.path_from_uuid(file_id_4)) is not None

    # Mark the first session as deleted
    api_db['sessions'].find_one_and_update(
        {'_id': ObjectId(session_id)},
        {'$set': {'deleted': d}}
    )

    # now the fourth file will be deleted too
    cleanup_deleted.main('--log-level', 'DEBUG', '--all')
    assert config.primary_storage.get_file_info(file_id_4, util.path_from_uuid(file_id_4)) is None
