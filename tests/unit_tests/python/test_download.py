import cStringIO
import datetime
import tarfile

import webob.exc

from mock import MagicMock
from requests import exceptions

from api.data_export.file_filter import file_filter_check, filtered_files

def test_file_filter_check():
    # null
    assert file_filter_check({'+': ['null']}, [])
    assert not file_filter_check({'+': ['null']}, ['foo'])

    # not null
    assert file_filter_check({'-': ['null']}, [])
    assert not file_filter_check({'-': ['null']}, ['foo'])

    # includes
    assert file_filter_check({'+': ['test']}, ['test'])
    assert file_filter_check({'+': ['test']}, ['foo', 'test'])
    assert not file_filter_check({'+': ['test']}, ['foo', 'bar'])

    # excludes
    assert not file_filter_check({'-': ['test']}, ['test'])
    assert not file_filter_check({'-': ['test']}, ['foo', 'test'])
    assert file_filter_check({'-': ['test']}, ['foo', 'bar'])
    assert file_filter_check({'-': ['test']}, [])

    # Combinations
    assert file_filter_check({'+': ['test'], '-': ['foo']}, ['test'])
    assert not file_filter_check({'+': ['test'], '-': ['foo']}, ['test', 'foo'])

def test_filtered_files():
    cont = {
        'inputs': [
            {'name': 'test.dcm', 'type': 'dicom'}
        ],
        'files': [
            {'name': 'test.csv', 'type': 'csv', 'tags': ['foo']},
            {'name': 'test2.csv', 'type': 'csv', 'tags': ['bar']},
            {'name': 'deleted.csv', 'type': 'csv', 'deleted': datetime.datetime.now()},
            {'name': 'test.nii', 'type': 'nifti', 'tags': ['foo', 'bar']}
        ]
    }

    def filter_files(spec):
        return set([ (group, f['name']) for group, f in filtered_files(cont, spec) ])

    result = filter_files([{'types': {'+': ['dicom']}}])
    assert result == set([('input', 'test.dcm')])

    result = filter_files([{'tags': {'-': ['bar']}}])
    assert result == set([('input', 'test.dcm'), ('output', 'test.csv')])

    result = filter_files([{'types': {'+': ['csv']}}, {'tags': {'+': ['foo']}}])
    assert result == set([('output', 'test.csv'), ('output', 'test2.csv'), ('output', 'test.nii')])


def test_archive_stream(mocker, data_builder, file_form, as_drone, randstr, with_site_settings):
    class MockRead:
        def __init__(self):
            self._read = False

        def __call__(self, b):
            if not self._read:
                self._read = True
                return 'test'
            return ''

    mocker.patch('api.dao.containerutil.verify_master_subject_code')

    get_return_value = MagicMock()
    get_return_value.read = MockRead()
    get_return_value.closed = False
    get_return_value.status = 200
    get_return_value.reason = 'OK'
    get_return_value.readable.return_value = True
    mock_is_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.is_signed_url', return_value=True)
    mock_get_signed = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_signed_url', return_value='url')
    mock_get_info = mocker.patch('api.storage.py_fs.py_fs_storage.PyFsStorage.get_file_info', return_value={'filesize': 100})

    project = data_builder.create_project(label='project1')
    # since partialFilterExpression on unique compound indexes doesn't work with mongomock,
    # provide these fields explicitly
    session = data_builder.create_session(label='session1', project=project,
        subject={'code': randstr(), 'master_code': randstr()})
    session2 = data_builder.create_session(label='session1', project=project,
        subject={'code': randstr(), 'master_code': randstr()})
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session2)

    # upload the same file to each container created and use different tags to
    # facilitate download filter tests:
    # acquisition: [], session: ['plus'], project: ['plus', 'minus']
    file_name = 'test.csv'
    as_drone.post('/acquisitions/' + acquisition + '/files', POST=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    as_drone.post('/acquisitions/' + acquisition2 + '/files', POST=file_form(
        file_name, meta={'name': file_name, 'type': 'csv'}))

    r = as_drone.post('/download', json={
        'optional': False,
        'nodes': [
            {'level': 'acquisition', '_id': acquisition},
            {'level': 'acquisition', '_id': acquisition2},
        ]
    })
    assert r.ok
    ticket = r.json['ticket']

    with mocker.patch('urllib3.PoolManager.request', return_value=get_return_value) as mocked_session:
        # Perform the download
        r = as_drone.get('/download?ticket=%s' % ticket)
        assert r.ok

        tar_file = cStringIO.StringIO(r.body)
        tar = tarfile.open(mode="r", fileobj=tar_file)

        # Verify a single file in tar with correct file name
        tarinfo_list = list(tar)
        # it contains two files
        assert len(tarinfo_list) == 2

        assert mock_is_signed.called
        assert get_return_value.read._read

    get_return_value = MagicMock()
    get_return_value.closed = False
    get_return_value.status = 200
    get_return_value.reason = 'OK'
    get_return_value.readable.return_value = True
    get_return_value.read.side_effect = exceptions.ConnectionError()

    with mocker.patch('urllib3.PoolManager.request', return_value=get_return_value) as mocked_session:
        r = as_drone.post('/download', json={
            'optional': False,
            'nodes': [
                {'level': 'acquisition', '_id': acquisition},
                {'level': 'acquisition', '_id': acquisition2},
            ]
        })
        assert r.ok
        ticket = r.json['ticket']

        # Perform the download
        r = as_drone.get('/download?ticket=%s' % ticket)
        try:
            assert r.body
        except webob.exc.HTTPInternalServerError as e:
            assert (str(e).startswith('Error happened during sending file content in archive stream'))
