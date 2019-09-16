import cStringIO
import datetime
import json
import os
import tarfile
import time
import zipfile

from bson.objectid import ObjectId
import pytest
from requests_toolbelt.multipart.decoder import MultipartDecoder

from api import config, util

BYTES_IN_MEGABYTE = float(1<<20)

def tarfile_members(contents):
    tar_file = cStringIO.StringIO(contents)
    tar = tarfile.open(mode="r", fileobj=tar_file)

    # Verify a single file in tar with correct file name
    result = {}
    for tarinfo in tar:
        fileobj = tar.extractfile(tarinfo.name)
        data = fileobj.read()
        fileobj.close()

        result[tarinfo.name] = data
    tar.close()

    return result

def test_download_k(data_builder, file_form, as_admin, as_user, api_db, with_site_settings):
    project = data_builder.create_project(label='project1')
    subject = data_builder.create_subject(code='subject1', project=project)
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    session2 = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    session3 = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    session4 = data_builder.create_session(label='session/1', project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)
    acquisition3 = data_builder.create_acquisition(session=session3)
    acquisition4 = data_builder.create_acquisition(session=session4)

    # upload the same file to each container created and use different tags to
    # facilitate download filter tests:
    # acquisition: [], session: ['plus'], project: ['plus', 'minus']
    as_admin.post('/projects/' + project + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})
    file_name = 'test.csv'
    as_user.post('/acquisitions/' + acquisition + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    as_user.post('/acquisitions/' + acquisition2 + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    as_user.post('/acquisitions/' + acquisition3 + '/files', files=file_form(
        'test.txt', meta={'name': file_name, 'type': 'text'}))

    as_user.post('/acquisitions/' + acquisition4 + '/files', files=file_form(
        'test.txt', meta={'name': file_name, 'type': 'text'}))

    as_user.post('/sessions/' + session + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['plus']}))

    as_user.post('/projects/' + project + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['plus', 'minus']}))

    # also a deleted file to make sure it doesn't show up
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        file_name, meta={'name': 'deleted_'+file_name, 'type': 'csv'}))
    r = as_admin.delete('/acquisitions/' + acquisition + '/files/deleted_' + file_name)
    assert r.ok

    missing_object_id = '000000000000000000000000'

    # Try to download w/ nonexistent ticket
    r = as_user.get('/download', params={'ticket': missing_object_id})
    assert r.status_code == 404

    # Retrieve a ticket for a batch download as superuser
    r = as_admin.post('/download', json={
        'optional': False,
        'filters': [{'tags': {
            '-': ['minus']
        }}],
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform the download
    r = as_admin.get('/download', params={'ticket': ticket})
    assert r.ok

    # Retrieve a ticket for a batch download
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [{'tags': {
            '-': ['minus']
        }}],
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform the download
    r = as_user.get('/download', params={'ticket': ticket})
    assert r.ok

    tar_file = cStringIO.StringIO(r.content)
    tar = tarfile.open(mode="r", fileobj=tar_file)

    # Verify a single file in tar with correct file name
    found_second_session = False
    found_third_session = False
    found_fourth_session = False
    for tarinfo in tar:
        assert os.path.basename(tarinfo.name) == file_name
        if 'session1_0' in str(tarinfo.name):
            found_second_session = True
        if 'session1_1' in str(tarinfo.name):
            found_third_session = True
        if 'session1_2' in str(tarinfo.name):
            found_fourth_session = True
    assert found_second_session
    assert found_third_session
    assert found_fourth_session
    tar.close()

    # Download one session with many acquisitions and make sure they are in the same subject folder

    acquisition3 = data_builder.create_acquisition(session=session)
    r = as_user.post('/acquisitions/' + acquisition3 + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))
    assert r.ok

    r = as_user.post('/download', json={
        'optional': False,
        'nodes': [
            {'level': 'acquisition', '_id': acquisition},
            {'level': 'acquisition', '_id': acquisition3},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform the download
    r = as_user.get('/download', params={'ticket': ticket})
    assert r.ok

    tar_file = cStringIO.StringIO(r.content)
    tar = tarfile.open(mode="r", fileobj=tar_file)

    # Verify a single file in tar with correct file name
    found_second_session = False
    for tarinfo in tar:
        assert os.path.basename(tarinfo.name) == file_name
        if 'session1_0' in str(tarinfo.name):
            found_second_session = True
    assert not found_second_session

    tar.close()

    # Try to perform the download from a different IP
    update_result = api_db.downloads.update_one(
        {'_id': ticket},
        {'$set': {'ip': '255.255.255.255'}})
    assert update_result.modified_count == 1

    r = as_user.get('/download', params={'ticket': ticket})
    assert r.status_code == 400

    # Try to retrieve a ticket referencing nonexistent containers
    r = as_user.post('/download', json={
        'optional': False,
        'nodes': [
            {'level': 'project', '_id': missing_object_id},
            {'level': 'session', '_id': missing_object_id},
            {'level': 'acquisition', '_id': missing_object_id},
        ]
    })
    assert r.status_code == 404

    # Try to retrieve ticket for bulk download w/ invalid container name
    # (not project|session|acquisition)
    r = as_user.post('/download', params={'bulk': 'true'}, json={
        'files': [{'container_name': 'collection', 'container_id': missing_object_id, 'filename': 'nosuch.csv'}]
    })
    assert r.status_code == 400

    # Try to retrieve ticket for bulk download referencing nonexistent file
    r = as_user.post('/download', params={'bulk': 'true'}, json={
        'files': [{'container_name': 'project', 'container_id': project, 'filename': 'nosuch.csv'}]
    })
    assert r.status_code == 404

    # Retrieve ticket for bulk download
    r = as_user.post('/download', params={'bulk': 'true'}, json={
        'files': [{'container_name': 'project', 'container_id': project, 'filename': file_name}]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform the download using symlinks
    r = as_user.get('/download', params={'ticket': ticket, 'symlinks': 'true'})
    assert r.ok


    # test missing file handling
    api_db.acquisitions.update_one({'_id': ObjectId(acquisition)},
        {'$set': {'files.0._id': 'not_available'}})

    r = as_user.post('/download', json={
        'optional': False,
        'nodes': [
            {'level': 'acquisition', '_id': acquisition},
            {'level': 'acquisition', '_id': acquisition3},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform the download
    r = as_user.get('/download', params={'ticket': ticket})
    assert r.ok

    tar_file = cStringIO.StringIO(r.content)
    tar = tarfile.open(mode="r", fileobj=tar_file)

    # Verify a single file in tar with correct file name
    tarinfo_list = list(tar)
    # it contains two files
    assert len(tarinfo_list) == 2
    assert len([tarinfo for tarinfo in tarinfo_list if tarinfo.name.endswith('.MISSING')]) == 1

    tar.close()


def test_filelist_download(data_builder, file_form, as_user, as_admin, with_site_settings):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)

    # Add User to permissions
    as_admin.post('/projects/' + project + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})

    zip_cont = cStringIO.StringIO()
    with zipfile.ZipFile(zip_cont, 'w') as zip_file:
        zip_file.writestr('two.csv', 'sample\ndata\n')
    zip_cont.seek(0)
    session_files = '/sessions/' + session + '/files'
    as_user.post(session_files, files=file_form('one.csv'))
    as_user.post(session_files, files=file_form(('two.zip', zip_cont)))

    # try to get non-existent file (Use admin because the user permissions is checked)
    r = as_user.get(session_files + '/non-existent.csv')
    assert r.status_code == 404

    # try to get file w/ non-matching hash
    r = as_user.get(session_files + '/one.csv', params={'hash': 'match me if you can'})
    assert r.status_code == 409

    # get download ticket for single file
    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single file w/ ticket
    r = as_user.get(session_files + '/one.csv', params={'ticket': ticket})
    assert r.ok

    # try to get zip info for non-zip file
    r = as_user.get(session_files + '/one.csv', params={'ticket': ticket, 'info': 'true'})
    assert r.status_code == 400

    # try to get zip member of non-zip file
    r = as_user.get(session_files + '/one.csv', params={'ticket': ticket, 'member': 'hardly'})
    assert r.status_code == 400

    # try to download a different file w/ ticket
    r = as_user.get(session_files + '/two.zip', params={'ticket': ticket})
    assert r.status_code == 400

    # get download ticket for zip file
    r = as_user.get(session_files + '/two.zip', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # get zip info
    r = as_user.get(session_files + '/two.zip', params={'ticket': ticket, 'info': 'true'})
    assert r.ok

    # try to get non-existent zip member
    r = as_user.get(session_files + '/two.zip', params={'ticket': ticket, 'member': 'hardly'})
    assert r.status_code == 400

    # get zip member
    r = as_user.get(session_files + '/two.zip', params={'ticket': ticket, 'member': 'two.csv'})
    assert r.ok

def test_filelist_range_download(data_builder, as_user, as_admin, file_form, with_site_settings):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)

    # Add user to permissions
    as_admin.post('/projects/' + project + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})

    session_files = '/sessions/' + session + '/files'
    as_user.post(session_files, files=file_form(('one.csv', '123456789')))

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # verify contents
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket})
    assert r.ok
    assert r.content == '123456789'

    # download single file from byte 0 to end of file
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single file's first byte by using lower case header
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'range': 'bytes=0-0'})
    assert r.ok
    assert r.content == '1'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single file's first two byte
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-1'})
    assert r.ok
    assert r.content == '12'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid unit
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'lol=-5'})
    assert r.status_code == 200
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range where the last byte is greater then the size of the file
    # in this case the whole file is returned
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-500'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range where the first byte is greater then the size of the file
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=500-'})
    assert r.status_code == 416

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range first byte is greater than the last one
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=10-5'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range header syntax
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes-1+5'})
    assert r.ok
    assert r.content == '123456789'


@pytest.mark.skipif(not os.getenv('SCITRAN_PERSISTENT_FS_URL', 'osfs').startswith('osfs'),
                    reason="Only OSFS supports all of these special range formats.")
def test_filelist_advanced_range_download(data_builder, as_user, as_admin, file_form, with_site_settings):
    # We run this test only with OSFS because other backends don't support fully the RFS standard.
    # Left comments about the found defects with the specific storage backends at the assertions.
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)

    # Add User to permissions
    as_admin.post('/projects/' + project + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})

    session_files = '/sessions/' + session + '/files'
    as_user.post(session_files, files=file_form(('one.csv', '123456789')))

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single file's last 5 bytes
    # ASFS returns the whole file, since it doesn't support this range format
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=-5'})
    assert r.ok
    assert r.content == '56789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range, in this case the whole file is returned
    # ASFS returns with status code 416
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=-'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range, can't parse first byte
    # ASFS returns with status code 400
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=r-0'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range, can't parse last byte
    # ASFS returns with status code 400
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-bb'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # try to download single file with invalid range syntax
    # ASFS returns with status code 400
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=1+5'})
    assert r.ok
    assert r.content == '123456789'

    r = as_user.get(session_files + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download multiple ranges
    # GCSFS doesn't support multiple ranges
    r = as_user.get(session_files + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=1-2, 3-4'})
    assert r.ok
    boundary = r.headers.get('Content-Type').split('boundary=')[1]
    assert r.content == '--{0}\n' \
                        'Content-Type: text/csv\n' \
                        'Content-Range: bytes 1-2/9\n\n' \
                        '23\n' \
                        '--{0}\n' \
                        'Content-Type: text/csv\n' \
                        'Content-Range: bytes 3-4/9\n\n' \
                        '45\n'.format(boundary)

def test_analysis_download(data_builder, file_form, as_user, as_admin, as_drone, default_payload, with_site_settings):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    zip_cont = cStringIO.StringIO()
    with zipfile.ZipFile(zip_cont, 'w') as zip_file:
        zip_file.writestr('two.csv', 'sample\ndata\n')
    zip_cont.seek(0)

    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': user_id
    }).ok

    # create (legacy) analysis for testing the download functionality
    r = as_user.post('/sessions/' + session + '/analyses', files=file_form('one.csv', ('two.zip', zip_cont), meta={
        'label': 'test',
        'inputs': [{'name': 'one.csv'}],
        'outputs': [{'name': 'two.zip'}],
    }))
    assert r.ok
    analysis = r.json()['_id']

    analysis_inputs = '/sessions/' + session + '/analyses/' + analysis + '/inputs'
    analysis_outputs = '/sessions/' + session + '/analyses/' + analysis + '/files'
    new_analysis_inputs = '/analyses/' + analysis + '/inputs'
    new_analysis_outputs = '/analyses/' + analysis + '/files'

    # Check that analysis inputs are placed under the inputs key
    r = as_user.get('/sessions/' + session + '/analyses/' + analysis)
    assert r.ok
    assert [f['name'] for f in r.json().get('inputs', [])] == ['one.csv']

    # try to download analysis inputs w/ non-existent ticket
    r = as_user.get(analysis_inputs, params={'ticket': '000000000000000000000000'})
    assert r.status_code == 404

    # get analysis batch download ticket for all inputs
    # Endpoint should no longer exist
    r = as_user.get(analysis_inputs, params={'ticket': ''}, json={"optional":True,"nodes":[{"level":"analysis","_id":analysis}]})
    assert r.status_code == 404

    ### Using '/download' endpoint only - for analysis outputs only! ###
    # try to download analysis outputs w/ non-existent ticket
    r = as_user.get('/download', params={'ticket': '000000000000000000000000'})
    assert r.status_code == 404

    # get analysis batch download ticket for all outputs
    r = as_user.get('/download', params={'ticket': ''}, json={"optional":True,"nodes":[{"level":"analysis","_id":analysis}]})
    assert r.ok
    ticket = r.json()['ticket']

    # filename is analysis_<label> not analysis_<_id>
    assert r.json()['filename'] == 'analysis_test.tar'

    # make sure user without permissions can't download
    assert as_admin.delete('/projects/' + project +'/permissions/' + user_id).ok
    r = as_user.get('/download', params={'ticket': ''}, json={"optional":True,"nodes":[{"level":"analysis","_id":analysis}]})
    assert r.status_code == 404

    # add user back to project
    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': user_id
    }).ok

    # batch download analysis outputs w/ ticket
    r = as_user.get('/download', params={'ticket': ticket})
    assert r.ok

    # Check to make sure inputs and outputs are in tar
    with tarfile.open(mode='r', fileobj=cStringIO.StringIO(r.content)) as tar:
        assert set([m.name for m in tar.getmembers()]) == set(['test/input/one.csv', 'test/output/two.zip'])

    # try to get download ticket for non-existent analysis file
    r = as_user.get(analysis_inputs + '/non-existent.csv')
    assert r.status_code == 404

    # get analysis download ticket for single file
    r = as_user.get(analysis_inputs + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single analysis file w/ ticket
    r = as_user.get(analysis_inputs + '/one.csv', params={'ticket': ticket})
    assert r.ok

    # try to get zip info for non-zip file
    r = as_user.get(analysis_inputs + '/one.csv', params={'ticket': ticket, 'info': 'true'})
    assert r.status_code == 400

    # try to get zip member of non-zip file
    r = as_user.get(analysis_inputs + '/one.csv', params={'ticket': ticket, 'member': 'nosuch'})
    assert r.status_code == 400

    # try to download a different file w/ ticket
    r = as_user.get(analysis_outputs + '/two.zip', params={'ticket': ticket})
    assert r.status_code == 400

    # get analysis download ticket for zip file
    r = as_user.get(analysis_outputs + '/two.zip', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # get zip info
    r = as_user.get(analysis_outputs + '/two.zip', params={'ticket': ticket, 'info': 'true'})
    assert r.ok

    # try to get non-existent zip member
    r = as_user.get(analysis_outputs + '/two.zip', params={'ticket': ticket, 'member': 'nosuch'})
    assert r.status_code == 400

    # get zip member
    r = as_user.get(analysis_outputs + '/two.zip', params={'ticket': ticket, 'member': 'two.csv'})
    assert r.ok

    ### single file analysis download using FileListHandler ###
    # try to get download ticket for non-existent analysis file
    r = as_user.get(new_analysis_inputs + '/non-existent.csv')
    assert r.status_code == 404

    # get analysis download ticket for single file
    r = as_user.get(new_analysis_inputs + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # download single analysis file w/ ticket
    r = as_user.get(new_analysis_inputs + '/one.csv', params={'ticket': ticket})
    assert r.ok

    # try to get zip info for non-zip file
    r = as_user.get(new_analysis_inputs + '/one.csv', params={'ticket': ticket, 'info': 'true'})
    assert r.status_code == 400

    # try to get zip member of non-zip file
    r = as_user.get(new_analysis_inputs + '/one.csv', params={'ticket': ticket, 'member': 'nosuch'})
    assert r.status_code == 400

    # try to download a different file w/ ticket
    r = as_user.get(new_analysis_outputs + '/two.zip', params={'ticket': ticket})
    assert r.status_code == 400

    # get analysis download ticket for zip file
    r = as_user.get(new_analysis_outputs + '/two.zip', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # get zip info
    r = as_user.get(new_analysis_outputs + '/two.zip', params={'ticket': ticket, 'info': 'true'})
    assert r.ok

    # try to get non-existent zip member
    r = as_user.get(new_analysis_outputs + '/two.zip', params={'ticket': ticket, 'member': 'nosuch'})
    assert r.status_code == 400

    # get zip member
    r = as_user.get(new_analysis_outputs + '/two.zip', params={'ticket': ticket, 'member': 'two.csv'})
    assert r.ok

    # delete session analysis (job)
    r = as_user.delete('/sessions/' + session + '/analyses/' + analysis)
    assert r.ok


def test_analyses_range_download(data_builder, as_user, as_admin, file_form, with_site_settings):
    project = data_builder.create_project()
    session = data_builder.create_session(project=project)
    # Add User to permissions
    as_admin.post('/projects/' + project + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})
    zip_cont = cStringIO.StringIO()
    with zipfile.ZipFile(zip_cont, 'w') as zip_file:
        zip_file.writestr('two.csv', 'sample\ndata\n')
    zip_cont.seek(0)

    # create (legacy) analysis for testing the download functionality
    r = as_user.post('/sessions/' + session + '/analyses', files=file_form(('one.csv', '123456789'),
                                                                            ('two.zip', zip_cont),
                                                                            meta={
                                                                                'label': 'test',
                                                                                'inputs': [{'name': 'one.csv'}],
                                                                                'outputs': [{'name': 'two.zip'}],
                                                                            }))
    assert r.ok
    analysis = r.json()['_id']

    analysis_inputs = '/analyses/' + analysis + '/inputs'

    r = as_user.get(analysis_inputs + '/one.csv', params={'ticket': ''})
    assert r.ok
    ticket = r.json()['ticket']

    # verify contents
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket})
    assert r.ok
    assert r.content == '123456789'

    # download single file from byte 0 to end of file
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-'})
    assert r.ok
    assert r.content == '123456789'

    # download single file's first byte by using lower case header
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'range': 'bytes=0-0'})
    assert r.ok
    assert r.content == '1'

    # download single file's first two byte
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-1'})
    assert r.ok
    assert r.content == '12'

    # try to download single file with invalid unit
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'lol=-5'})
    assert r.status_code == 200
    assert r.content == '123456789'

    # try to download single file with invalid range where the last byte is greater then the size of the file
    # in this case the whole file is returned
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=0-500'})
    assert r.ok
    assert r.content == '123456789'

    # try to download single file with invalid range where the first byte is greater then the size of the file
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=500-'})
    assert r.status_code == 416

    # try to download single file with invalid range first byte is greater than the last one
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes=10-5'})
    assert r.ok
    assert r.content == '123456789'

    # try to download single file with invalid range header syntax
    r = as_user.get(analysis_inputs + '/one.csv',
                     params={'ticket': ticket, 'view': 'true'},
                     headers={'Range': 'bytes-1+5'})
    assert r.ok
    assert r.content == '123456789'


def test_filters(data_builder, file_form, as_user, as_admin, with_site_settings):

    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    acquisition2 = data_builder.create_acquisition()

    # Add User to permissions
    as_admin.post('/projects/' + project + '/permissions', json={'_id': 'user@user.com', 'access': 'admin'})

    as_user.post('/acquisitions/' + acquisition + '/files', files=file_form(
        "test.csv", meta={'name': "test.csv", 'type': 'csv', 'tags': ['red', 'blue']}))
    as_user.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'test.dicom', meta={'name': 'test.dicom', 'type': 'dicom', 'tags': ['red']}))
    as_user.post('/acquisitions/' + acquisition2 + '/files', files=file_form(
        'test.nifti', meta={'name': 'test.nifti', 'type': 'nifti'}))
    r = as_user.get('/acquisitions/' + acquisition)
    assert r.ok

    # Malformed filters
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'tags': 'red'}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.status_code == 400

    # No filters
    r = as_user.post('/download', json={
        'optional': False,
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.ok
    assert r.json()['file_cnt'] == 3

    # Filter by modified since
    now = int(time.time())
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'since': now - 1}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.ok
    assert r.json()['file_cnt'] == 3

    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'since': now + 1}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.status_code == 404

    # Filter by tags
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'tags': {'+':['red']}}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.ok
    assert r.json()['file_cnt'] == 2

    # Use filter aliases
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'tags': {'plus':['red']}}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.ok
    # 'plus' is same as using '+'
    assert r.json()['file_cnt'] == 2

    # Filter by type
    as_user.post('/acquisitions/' + acquisition + '/files', files=file_form(
        "test", meta={'name': "test", 'tags': ['red', 'blue']}))
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'types': {'+':['nifti']}}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.ok
    assert r.json()['file_cnt'] == 1
    r = as_user.post('/download', json={
        'optional': False,
        'filters': [
            {'types': {'+':['null']}}
        ],
        'nodes': [
            {'level': 'session', '_id': session},
        ]
    })
    assert r.ok
    assert r.json()['file_cnt'] == 1

def test_summary(data_builder, as_user, as_admin, file_form, with_site_settings):
    project = data_builder.create_project(label='project1')
    session = data_builder.create_session(label='session1')
    session2 = data_builder.create_session(label='session1')
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)

    # add user to project
    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.post('/projects/' + project + '/permissions', json={
        'access': 'admin',
        '_id': user_id
    }).ok

    # upload the same file to each container created and use different tags to
    # facilitate download filter tests:
    # acquisition: [], session: ['plus'], project: ['plus', 'minus']
    file_name = 'test.csv'
    as_user.post('/acquisitions/' + acquisition + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    as_user.post('/acquisitions/' + acquisition2 + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    as_user.post('/sessions/' + session + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['plus']}))

    as_user.post('/projects/' + project + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['plus', 'minus']}))


    # also a deleted file to make sure it doesn't show up
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        file_name, meta={'name': 'deleted_'+file_name, 'type': 'csv'}))
    r = as_admin.delete('/acquisitions/' + acquisition + '/files/deleted_' + file_name)
    assert r.ok

    missing_object_id = '000000000000000000000000'

    r = as_user.post('/download/summary', json=[{"level":"project", "_id":project}])
    assert r.ok
    assert len(r.json()) == 1
    assert r.json().get("csv", {}).get("count",0) == 4

    r = as_user.post('/download/summary', json=[{"level":"session", "_id":session}])
    assert r.ok
    assert len(r.json()) == 1
    assert r.json().get("csv", {}).get("count",0) == 2

    r = as_user.post('/download/summary', json=[{"level":"acquisition", "_id":acquisition},{"level":"acquisition", "_id":acquisition2}])
    assert r.ok
    assert len(r.json()) == 1
    assert r.json().get("csv", {}).get("_id") == "csv"
    assert r.json().get("csv", {}).get("count",0) == 2

    r = as_user.post('/download/summary', json=[{"level":"group", "_id":missing_object_id}])
    assert r.status_code == 400

    r = as_user.post('/sessions/' + session + '/analyses',  files=file_form(
        file_name, meta={'label': 'test', 'outputs':[{'name':file_name}]}))
    assert r.ok
    analysis = r.json()['_id']

    r = as_user.post('/download/summary', json=[{"level":"analysis", "_id":analysis}])
    assert r.ok
    assert len(r.json()) == 1
    assert r.json().get("tabular data", {}).get("count",0) == 1

    assert as_admin.delete('/projects/' + project + '/permissions/' + user_id).ok
    r = as_user.post('/download/summary', json=[{"level":"analysis", "_id":analysis}])
    assert r.ok
    assert len(r.json()) == 0


def test_subject_download(data_builder, as_admin, file_form, with_site_settings):
    project = data_builder.create_project()
    session = data_builder.create_session(subject={'code': 'subject-download'})
    subject = as_admin.get('/sessions/' + session).json()['subject']['_id']

    as_admin.post('/projects/' + project + '/files', files=file_form('test1.txt'))
    as_admin.post('/subjects/' + subject + '/files', files=file_form('test2.txt'))
    as_admin.post('/sessions/' + session + '/files', files=file_form('test3.txt'))

    r = as_admin.post('/download/summary', json=[{'level': 'project', '_id': project}])
    assert r.ok
    assert len(r.json()) == 1
    assert r.json()['text']['count'] == 3

    r = as_admin.post('/download', json={'nodes': [{'level': 'project', '_id': project}], 'optional': False})
    assert r.ok
    assert r.json()['file_cnt'] == 3

    r = as_admin.post('/download/summary', json=[{'level': 'subject', '_id': subject}])
    assert r.ok
    assert len(r.json()) == 1
    assert r.json()['text']['count'] == 2

    r = as_admin.post('/download', json={'nodes': [{'level': 'subject', '_id': subject}], 'optional': False})
    assert r.ok
    assert r.json()['file_cnt'] == 2

def test_full_project_download(data_builder, file_form, as_admin, as_root, as_drone, api_db, with_site_settings):
    # Projects must have a provider for job/gear uploads to work
    gear = data_builder.create_gear(gear={'inputs': {'csv': {'base': 'file'}}})
    project = data_builder.create_project(label='project1', providers={'storage': 'deadbeefdeadbeefdeadbeef'})
    subject = data_builder.create_subject(code='subject1', project=project, type='animal', species='dog')
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    session2 = data_builder.create_session(label='session2', project=project, subject={'_id': subject})
    session3 = data_builder.create_session(label='session3', project=project, subject={'_id': subject})
    session4 = data_builder.create_session(label='session4', age=1234, project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(label='acquisition1', session=session)
    acquisition2 = data_builder.create_acquisition(label='acquisition2', session=session2)
    acquisition3 = data_builder.create_acquisition(label='acquisition3', session=session3)
    acquisition4 = data_builder.create_acquisition(label='acquisition4', session=session4)

    # Set metadata on session
    as_admin.post('/sessions/' + session + '/info', json={
        'replace': {
            'test': 'test_data'
        }
    })

    # upload the same file to each container created and use different tags to
    # facilitate download filter tests:
    file_name = 'test.csv'
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['acq1']}))

    as_admin.post('/acquisitions/' + acquisition2 + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    as_admin.post('/acquisitions/' + acquisition3 + '/files', files=file_form(
        'test.txt', meta={'name': file_name, 'type': 'text'}))

    as_admin.post('/acquisitions/' + acquisition4 + '/files', files=file_form(
        'test.txt', meta={'name': file_name, 'type': 'text'}))

    as_admin.post('/sessions/' + session + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['plus']}))

    as_admin.post('/projects/' + project + '/files', files=file_form(
        file_name, meta={'name': file_name, 'type': 'csv', 'tags': ['plus', 'minus']}))

    # also a deleted file to make sure it doesn't show up
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        file_name, meta={'name': 'deleted_'+file_name, 'type': 'csv'}))
    r = as_admin.delete('/acquisitions/' + acquisition + '/files/deleted_' + file_name)
    assert r.ok

    # Create analysis job at project level
    r = as_admin.post('/projects/' + project + '/analyses', json={
        'label': 'online',
        'job': {'gear_id': gear,
                'inputs': {'csv': {'type': 'acquisition', 'id': acquisition, 'name': 'test.csv'}}}
    })
    assert r.ok
    analysis1_id = r.json()['_id']

    # Engine upload
    r = as_admin.get('/analyses/' + analysis1_id)
    assert r.ok
    job = r.json().get('job')

    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis1_id, 'job': job},
        files=file_form('output.csv', meta={'type': 'tabular data'}))
    assert r.ok

    # Create ad-hoc analysis for session
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'analysis_label',
        'inputs': [
            {'type': 'acquisition', 'id': acquisition, 'name': 'test.csv'},
        ]
    })
    assert r.ok
    analysis2_id = r.json()['_id']

    # Manual upload
    r = as_admin.post('/analyses/' + analysis2_id + '/files', files=file_form('output1.csv', 'output2.csv', meta=[
        {'name': 'output1.csv', 'info': {'foo': 'foo'}},
        {'name': 'output2.csv', 'info': {'bar': 'bar'}},
    ]))
    assert r.ok

    # Test no match
    # Retrieve a ticket for a batch download
    r = as_admin.post('/download', params={'type': 'full', 'analyses': 'true', 'metadata': 'true'}, json={
        'filters': [{'tags': {
            '+': ['NONE-SUCH']
        }}],
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.status_code == 404

    # Retrieve a ticket for a batch download
    r = as_admin.post('/download', params={'type': 'full'}, json={
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Compare summary with & without metadata
    r = as_admin.post('/download/summary', params={'type': 'full'}, json=[{"level":"project", "_id":project}])
    assert r.ok
    no_metadata_summary = r.json()
    assert len(no_metadata_summary) == 2
    assert no_metadata_summary.get('csv', {}).get('count',0) == 4
    assert no_metadata_summary.get('csv', {}).get('mb_total',0) == 40 / BYTES_IN_MEGABYTE
    assert no_metadata_summary.get('text', {}).get('count',0) == 2
    assert no_metadata_summary.get('text', {}).get('mb_total',0) == 20 / BYTES_IN_MEGABYTE

    # Compare summary with & without metadata
    r = as_admin.post('/download/summary', params={'type': 'full', 'metadata': 'true'}, json=[{"level":"project", "_id":project}])
    assert r.ok
    assert r.json() == no_metadata_summary

    # Perform a download, without metadata
    r = as_admin.get('/download', params={'ticket': ticket})
    assert r.ok

    expected_files = {
        'flywheel/project1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/FILES/test.csv'
    }

    files = tarfile_members(r.content)
    assert set(files.keys()) == expected_files

    # Retrieve a ticket for a batch download
    r = as_admin.post('/download', params={'type': 'full', 'metadata': 'true'}, json={
        'filters': [{'tags': {
            '-': ['minus']
        }}],
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform a download, with metadata
    r = as_admin.get('/download', params={'ticket': ticket})
    assert r.ok

    expected_files = {
        'flywheel/project1/project1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/subject1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/session1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/session2.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/session3.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/session4.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/acquisition1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/acquisition2.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/acquisition3.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/acquisition4.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/FILES/test.csv.flywheel.json'
    }

    files = tarfile_members(r.content)
    assert set(files.keys()) == expected_files

    # Check contents of subject metadata
    subject_json = json.loads(files['flywheel/project1/SUBJECTS/subject1/subject1.flywheel.json'])
    assert '_id' not in subject_json
    assert subject_json['code'] == 'subject1'
    assert subject_json['type'] == 'animal'
    assert subject_json['species'] == 'dog'
    assert 'created' in subject_json
    assert 'modified' in subject_json

    # Check contents of session metadata
    session_json = json.loads(files['flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/session4.flywheel.json'])
    assert '_id' not in session_json
    assert session_json['label'] == 'session4'
    assert session_json['age'] == 1234
    assert 'created' in session_json
    assert 'modified' in session_json

    # Check contents of file metadata
    session_file_json = json.loads(files['flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv.flywheel.json'])
    assert '_id' not in session_file_json
    assert session_file_json['name'] == 'test.csv'
    assert session_file_json['size'] > 0
    assert session_file_json['type'] == 'csv'
    assert session_file_json['tags'] == ['acq1']
    assert 'created' in session_file_json
    assert 'modified' in session_file_json

    # Target a file on acquisition1, and ensure that no extraneous containers are generated
    # Retrieve a ticket for a batch download
    r = as_admin.post('/download', params={'type': 'full', 'metadata': 'true'}, json={
        'filters': [{'tags': {
            '+': ['acq1']
        }}],
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform a download, with metadata
    r = as_admin.get('/download', params={'ticket': ticket})
    assert r.ok

    expected_files = {
        'flywheel/project1/project1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/subject1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/session1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/acquisition1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv.flywheel.json'
    }

    files = tarfile_members(r.content)
    assert set(files.keys()) == expected_files

    # Retrieve a ticket for a batch download with metadata and analyses
    r = as_admin.post('/download', params={
        'type': 'full',
        'metadata': 'true',
        'analyses': 'true'
    }, json={
        'filters': [{'tags': {
            '-': ['minus']
        }}],
        'nodes': [
            {'level': 'project', '_id': project},
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    # Perform a download, with metadata
    r = as_admin.get('/download', params={'ticket': ticket})
    assert r.ok

    expected_files = {
        'flywheel/project1/project1.flywheel.json',
        'flywheel/project1/ANALYSES/online/online.flywheel.json',
        'flywheel/project1/ANALYSES/online/INPUT/test.csv',
        'flywheel/project1/ANALYSES/online/INPUT/test.csv.flywheel.json',
        'flywheel/project1/ANALYSES/online/OUTPUT/output.csv',
        'flywheel/project1/ANALYSES/online/OUTPUT/output.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/subject1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/session1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/session2.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/session3.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/session4.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/acquisition1.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/acquisition2.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/acquisition3.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/acquisition4.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/FILES/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ACQUISITIONS/acquisition1/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session2/ACQUISITIONS/acquisition2/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session3/ACQUISITIONS/acquisition3/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session4/ACQUISITIONS/acquisition4/FILES/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/analysis_label.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/INPUT/test.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/INPUT/test.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/OUTPUT/output1.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/OUTPUT/output1.csv.flywheel.json',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/OUTPUT/output2.csv',
        'flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/OUTPUT/output2.csv.flywheel.json'
    }

    files = tarfile_members(r.content)
    assert set(files.keys()) == expected_files

    # Test analysis input metadata
    analysis_input_json = json.loads(files['flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/INPUT/test.csv.flywheel.json'])
    assert '_id' not in analysis_input_json
    assert analysis_input_json['name'] == 'test.csv'
    assert analysis_input_json['size'] > 0
    assert analysis_input_json['type'] == 'csv'
    assert 'created' in analysis_input_json
    assert 'modified' in analysis_input_json

    # Test analysis output metadata
    analysis_output_json = json.loads(files['flywheel/project1/SUBJECTS/subject1/SESSIONS/session1/ANALYSES/analysis_label/OUTPUT/output1.csv.flywheel.json'])
    assert '_id' not in analysis_output_json
    assert analysis_output_json['name'] == 'output1.csv'
    assert analysis_output_json['size'] > 0
    assert analysis_output_json['type'] == 'tabular data'
    assert 'created' in analysis_output_json
    assert 'modified' in analysis_output_json

def test_download_targets(data_builder, as_admin, file_form):
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'file', meta={'name': 'file', 'type': 'csv', 'info': {'header': 'test'}}))

    r = as_admin.post('/download', params={'type': 'full', 'metadata': '1'}, json={
        'optional': False,
        'nodes': [
            {'level': 'project', '_id': project}
        ]
    })
    assert r.ok
    ticket = r.json()['ticket']

    r = as_admin.get('/download/' + ticket + '/targets', stream=True)
    assert r.ok
    r_parts = MultipartDecoder.from_response(r).parts

    # NOTE loading all targets instead of iterating for test code simplicity
    targets = [json.loads(part.content) for part in r_parts]
    targets.sort(key=lambda target: target['dst_path'], reverse=True)

    assert len(targets) == 6

    # check metadata sidecars (proj, subj, sess, acq and (acq) file metadata)
    for i, level in enumerate(('project', 'subject', 'session', 'acquisition', 'acquisition')):
        assert targets[i]['container_type'] == level
        assert targets[i]['download_type'] == 'metadata_sidecar'
        assert targets[i]['dst_path'].endswith('flywheel.json')
        assert 'metadata' in targets[i]

    assert targets[5]['container_type'] == 'acquisition'
    assert targets[5]['download_type'] == 'file'
    assert targets[5]['dst_path'].endswith('file')
    assert 'metadata' not in targets[5]
