"""Provides stream-based opening of download files"""
import certifi
import urllib3
import fs.errors
import flywheel_common.errors

from .. import files, config, io, access_log
from ..web.request import AccessType

class DownloadFileSource(object):
    """Abstraction for converting DownloadTargetS into a fileobj, and logging access.

    This class is iterable, and will return targets, ready to be opened with
    the open function. Order is not guaranteed, and should be optimized for
    retrieval wherever possible.

    This class should be extended to handle the different download types.
    """
    def __init__(self, ticket, request):
        """Create a new download file source.

        Args:
            ticket (DownloadTicket): The download ticket
            request (object): The request object
        """
        self.ticket = ticket
        self.targets = ticket.targets

        self.request = request

        # TODO: Sort the set of targets such that we can batch retrieve one
        # set of containers at a time to resolve info/file_info
        self._index = 0
        self._count = len(self.targets)

        # Connection pool for signed urls, require valid certificates, using certifi store
        # See: https://urllib3.readthedocs.io/en/latest/user-guide.html#certificate-verification
        self._http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= self._count:
            raise StopIteration()

        result = self.targets[self._index]
        self._index += 1
        return result

    def next(self):
        return self.__next__()

    def open(self, target):
        """Open the given DownloadTarget, returning a file-like object.

        NOTE: It is considered an error to pass a target to this function that hasn't been
        returned via the iterator protocol.

        Args:
            target (DownloadTarget): The download target to open for reading

        Returns:
            file: The file-like ContextManager, that supports read

        Raises:
            OSError: If the file could not be opened
        """
        if target.download_type == 'file':
            # Log access before accessing the file, raises and aborts the request if that fails
            access_log.log_user_access(self.request, AccessType.download_file, cont_name=target.container_type,
                cont_id=target.container_id, filename=target.dst_name, origin=self.ticket.origin,
                download_ticket=self.ticket.ticket_id)

            return self._open_file(target)
        else:
            raise OSError('Unexpected download type: {}'.format(target.download_type))

    def _open_file(self, target):
        """Open the given download 'file' target"""
        # TODO: For now, this is an optimization - directly accessing the signed url
        # can speed up transfer. Shouldn't open for reading basically do this?
        signed_url = None
        if config.primary_storage.is_signed_url():
            try:
                filehash = None
                if not target.file_id:
                    filehash = config.primary_storage.get_file_hash(None, target.src_path)
                signed_url = config.primary_storage.get_signed_url(target.file_id, file_hash=filehash)
            except fs.errors.ResourceNotFound:
                pass
            except flywheel_common.errors.ResourceNotFound:
                pass
        try:
            if signed_url:
                return io.URLFileWrapper(signed_url, self._http)
            else:
                file_system = files.get_fs_by_file_info(target.file_id, target.file_hash)
                filehash = None
                if not target.file_id:
                    filehash = file_system.get_file_hash(None, target.src_path)
                return file_system.open(target.file_id, 'rb', filehash)
        except (fs.errors.ResourceNotFound,
                fs.errors.OperationFailed,
                IOError) as err:
            # Contract is to raise an OSError if we cannot open the file
            raise OSError(str(err))
