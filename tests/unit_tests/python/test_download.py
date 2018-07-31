import cStringIO
import tarfile

import webob.exc

from mock import MagicMock
from requests import exceptions


def test_archive_stream(mocker, data_builder, file_form, as_drone):
    def iter_content_mock():
        yield 'test'

    get_return_value = MagicMock()
    get_return_value.iter_content.return_value = iter_content_mock()
    mocked_files = mocker.patch('api.files.get_signed_url')

    project = data_builder.create_project(label='project1')
    session = data_builder.create_session(label='session1', project=project)
    session2 = data_builder.create_session(label='session1', project=project)
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

    with mocker.patch('api.download.requests.Session.get', return_value=get_return_value) as mocked_session:
        # Perform the download
        r = as_drone.get('/download?ticket=%s' % ticket)
        assert r.ok

        tar_file = cStringIO.StringIO(r.body)
        tar = tarfile.open(mode="r", fileobj=tar_file)

        # Verify a single file in tar with correct file name
        tarinfo_list = list(tar)
        # it contains two files
        assert len(tarinfo_list) == 2

        assert mocked_files.called
        assert get_return_value.iter_content.called

    def iter_content_error_mock():
        yield 'test'
        raise exceptions.ConnectionError()

    get_return_value = MagicMock()
    get_return_value.iter_content.return_value = iter_content_error_mock()

    with mocker.patch('api.download.requests.Session.get', return_value=get_return_value) as mocked_session:
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
