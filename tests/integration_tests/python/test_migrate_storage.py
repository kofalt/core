import os
import shutil
import sys

import fs.move
import fs.path
import pytest

from api import util
from api.site.storage_provider_service import StorageProviderService
from api.site.providers import get_provider
from bson.objectid import ObjectId

# When we move a file we also need to update the provider Id now
def move_file(src_storage, src_id, dst_storage, dst_path):
    src_path = util.path_from_uuid(src_id)
    target_dir = fs.path.dirname(dst_path)
    with src_storage.storage_plugin.open(src_id, src_path, 'rb') as src_fp, dst_storage.storage_plugin.open(None, dst_path, 'wb') as dst_fp:
        shutil.copyfileobj(src_fp, dst_fp)
    src_storage.storage_plugin.remove_file(src_id, src_path)

# Local storage uses the V1 naming not CAS
def move_file_to_local(src_storage, src_id, dst_path):
    storage_service = StorageProviderService()
    storage = storage_service.get_temp_storage()
    move_file(src_storage, src_id, storage.storage_plugin, dst_path)

@pytest.fixture(scope='function')
def migrate_storage(mocker):
    """Enable importing from `bin` and return `migrate_storage`."""
    bin_path = os.path.join(os.getcwd(), 'bin', 'oneoffs')
    mocker.patch('sys.path', [bin_path] + sys.path)
    import migrate_storage
    return migrate_storage


@pytest.yield_fixture(scope='function')
def gears_to_migrate(api_db, as_admin, randstr, file_form):
    def gen_gear_meta(gear_name):
        return {'gear': {
            "version": '0.0.1',
            "config": {},
            "name": gear_name,
            "inputs": {
                "file": {
                    "base": "file",
                    "description": "Any image."
                }
            },
            "maintainer": "Test",
            "description": "Test",
            "license": "Other",
            "author": "Test",
            "url": "http://example.example",
            "label": "Test Gear",
            "flywheel": "0",
            "source": "http://example.example"
        }}

    gears = []

    gear_name_2 = randstr()
    file_name = '%s.tar.gz' % randstr()
    file_content = randstr()
    r = as_admin.post('/gears/temp', files=file_form((file_name, file_content), meta=gen_gear_meta(gear_name_2)))
    gear_id_2 = r.json()['_id']

    r = as_admin.get('/gears/' + gear_id_2)
    gear_json_2 = r.json()

    file_id_2 = gear_json_2['exchange']['rootfs-id']
    file_provider_id_2 = gear_json_2['exchange']['rootfs-provider-id']

    gears.append((gear_id_2, file_id_2, file_provider_id_2))

    yield gears

    # clean up
    gear_json_2 = api_db['gears'].find_one({'_id': ObjectId(gear_id_2)})
    files_to_delete = []
    files_to_delete.append((gear_json_2['exchange'].get('rootfs-id'), file_provider_id_2))

    for f_id, f_provider_id in files_to_delete:
        try:
            source_fs = get_provider(f_provider_id).storage_plugin
            source_fs.remove_file(f_id, None)
        except:
            pass

    api_db['gears'].delete_one({'_id': ObjectId(gear_id_2)})

@pytest.yield_fixture(scope='function')
def files_to_migrate(data_builder, api_db, as_admin, randstr, file_form):
    # Create a project
    session_id = data_builder.create_session()

    files = []

    # Create an UUID file
    file_name_1 = '%s.csv' % randstr()
    file_content_1 = randstr()
    as_admin.post('/sessions/' + session_id + '/files', files=file_form((file_name_1, file_content_1)))

    file_info = api_db['sessions'].find_one(
        {'files.name': file_name_1}
    )['files'][0]
    file_id_1 = file_info['_id']
    url_1 = '/sessions/' + session_id + '/files/' + file_name_1

    files.append((session_id, file_name_1, url_1, util.path_from_uuid(file_id_1), str(file_info['provider_id']), file_id_1))

    yield files

    # Clean up, get the files
    files = api_db['sessions'].find_one(
        {'_id': ObjectId(session_id)}
    )['files']
    # Delete the files but the session still exists in the DB with now missing data
    for f in files:
        try:
            source_fs = get_provider(f['provider_id']).storage_plugin
            source_fs.remove_file(f['_id'], None)
        except:
            pass


def test_migrate_containers(
    files_to_migrate, as_admin, migrate_storage, second_storage_provider):
    """Testing collection migration"""
    # get file stored by uuid in storage
    (_, _, url_2, file_path_2, src_provider_id, file_id_2) = files_to_migrate[0]

    source_fs = get_provider(src_provider_id).storage_plugin
    dest_fs = get_provider(second_storage_provider).storage_plugin

    # get the ticket
    r = as_admin.get(url_2, params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']
    # download the file
    assert as_admin.get(url_2, params={'ticket': ticket}).ok

    # run the migration
    migrate_storage.main(
        '--containers',
        '--source', src_provider_id,  # Filters on id to avoid migrating other test data in DB
        '--destination', second_storage_provider
    )
    # Verify source file is not deleted
    assert source_fs.get_file_info(file_id_2, None) is not None

    # delete files from the source storage to clean up
    source_fs.remove_file(file_id_2, None)

    # Verify file was moved to destination
    assert dest_fs.get_file_info(file_id_2, None) is not None

    # get the files from the new filesystem
    # get the ticket
    r = as_admin.get(url_2, params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']
    # download the file
    assert as_admin.get(url_2, params={'ticket': ticket}).ok

def test_migrate_containers_error(files_to_migrate, migrate_storage, second_storage_provider):
    """Testing that the migration script throws an exception if it couldn't migrate a file"""

    #For now we will get the only provider in the system which is osfs for local file minipulation
    storage_service = StorageProviderService()
    local_fs = storage_service.determine_provider(None, None, force_site_provider=True).storage_plugin

    # get the file to migrate
    (_, _, _, file_path_1, provider_id, file_id) = files_to_migrate[0]

    # delete the file from the filesystem but its still associated with the acquisition
    local_fs.remove_file(file_id, None)

    # Migrating with missing data files will error
    with pytest.raises(Exception):
        migrate_storage.main('--containers', '--destination', second_storage_provider)

    #This session will continue to exist in the DB with defunt data 


def test_migrate_gears(gears_to_migrate, as_admin, migrate_storage, with_site_settings, second_storage_provider):
    """Testing collection migration"""

    (gear_id_1, gear_file_id_1, gear_file_provider_id_1) = gears_to_migrate[0]

    # get gears before migration
    assert as_admin.get('/gears/temp/' + gear_id_1).ok

    # run migration
    migrate_storage.main('--gears', '--destination' , second_storage_provider)

    #delete files from the source storage
    source_fs = get_provider(gear_file_provider_id_1).storage_plugin
    source_fs.remove_file(gear_file_id_1, None)

    # get the files that will now be served from the new provider
    assert as_admin.get('/gears/temp/' + gear_id_1).ok


def test_migrate_gears_error(gears_to_migrate, migrate_storage, second_storage_provider):
    """Testing that the migration script throws an exception if it couldn't migrate a file"""

    # get the other file, so we can clean up
    (_, gear_file_id_2, gear_file_provider_id_2) = gears_to_migrate[0]

    # delete the file
    source_fs = get_provider(gear_file_provider_id_2).storage_plugin
    source_fs.remove_file(gear_file_id_2, None)

    with pytest.raises(Exception):
        migrate_storage.main('--gears', '--destination', second_storage_provider)

    #If the file is in an error we need to remove it from the system so future test are not clobbered



def test_migrate_analysis(files_to_migrate, as_admin, migrate_storage, default_payload, data_builder, file_form, second_storage_provider):
    """Testing analysis migration"""

    # get file storing by uuid in storage
    (session_id, file_name_2, url_2, file_path_2, provider_id_2, file_id_2) = files_to_migrate[0]

    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'csv': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    # create project analysis (job) using project's file as input
    r = as_admin.post('/sessions/' + session_id + '/analyses', json={
        'label': 'test analysis job',
        'job': {
            'gear_id': gear,
            'inputs': {
                'csv': {
                    'type': 'session',
                    'id': session_id,
                    'name': file_name_2
                }
            },
            'tags': ['example']
        }
    })
    assert r.ok
    analysis_id1 = r.json()['_id']

    r = as_admin.get('/sessions/' + session_id + '/analyses/' + analysis_id1)
    assert r.ok
    analysis_files1 = '/sessions/' + session_id + '/analyses/' + analysis_id1 + '/files'

    # run the migration
    migrate_storage.main('--containers', '--destination', second_storage_provider)

    # delete files from the local storage
    source_fs = get_provider(provider_id_2).storage_plugin
    source_fs.remove_file(file_id_2, None)

    # get the ticket
    r = as_admin.get(url_2, params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download the file from the new provider
    assert as_admin.get(url_2, params={'ticket': ticket}).ok

    # get analysis download ticket for single file
    r = as_admin.get(analysis_files1 + '/' + file_name_2, params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single analysis file w/ ticket
    r = as_admin.get(analysis_files1 + '/' + file_name_2, params={'ticket': ticket})
    assert r.ok

    r = as_admin.get('/sessions/' + session_id + '/analyses/' + analysis_id1)
    assert r.ok
    input_file_id = r.json()['inputs'][0]['_id']

    r = as_admin.get('/sessions/' + session_id)
    assert r.ok
    project_file_id = r.json()['files'][0]['_id']

    assert input_file_id == project_file_id

    #clean up the file on the disk but its still in the db so this will break future tests
    dest_fs = get_provider(second_storage_provider).storage_plugin
    dest_fs.remove_file(file_id_2, None)
