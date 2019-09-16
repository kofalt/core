# coding=utf-8
from api.dao.containerutil import ContainerReference
import mock


def test_container_reference_file_uri_should_not_raise_exception_if_unicode_in_filename():
    container_reference = ContainerReference('sessions', 'session-id')
    container_reference.get = mock.MagicMock()
    filename = u'åß∂.txt'

    file_uri = container_reference.file_uri(filename)

    assert file_uri == '/sessions/session-id/files/åß∂.txt'
