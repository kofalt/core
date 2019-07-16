"""Provides stream-based opening of download files"""
import copy
import json
import cStringIO

import certifi
import urllib3
import fs.errors
import flywheel_common.errors

from .. import io, access_log
from ..web.request import AccessType
from ..web.encoder import custom_json_serializer
from ..dao.containerstorage import cs_factory
from ..site.providers import get_provider

METADATA_BLACKLIST = [
    '_id', 'parents', 'collections', 'group', 'project', 'subject', 'session',
    'acquisition', 'origin', 'job', 'inputs', 'files'
]

def target_sort_key(target):
    """Return a sort key for the given download target

    Returns:
        tuple: The download type, and container type tuple
    """
    return (target.download_type, target.container_type)

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

        self._index = 0
        self._count = len(self.targets)

        # Sort the set of targets such that we can batch retrieve one
        # set of containers at a time to resolve info/file_info
        self.targets.sort(key=target_sort_key)

        # A pre-fetched set of containers
        # This is a map of container_type to map of containers by id
        self._containers = {}

        # Connection pool for signed urls, require valid certificates, using certifi store
        # See: https://urllib3.readthedocs.io/en/latest/user-guide.html#certificate-verification
        self._http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= self._count:
            raise StopIteration()

        result = self.targets[self._index]
        self._prefetch(result)
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
        elif target.download_type == 'metadata_sidecar':
            return self._open_metadata_sidecar(target)
        else:
            raise OSError('Unexpected download type: {}'.format(target.download_type))

    def _prefetch(self, target):
        """Prefetch all containers of the given type, if metadata is required"""
        # Right now assumes that anything other than files requires container fetch
        if target.download_type == 'file':
            return
        if target.container_type in self._containers:
            return

        # Execute on the sorted target list
        container_type = target.container_type
        ids = {target.container_id}
        i = self._index + 1
        while i < self._count:
            next_target = self.targets[i]
            if next_target.download_type != target.download_type or next_target.container_type != container_type:
                break
            ids.add(next_target.container_id)
            i += 1

        # Retrieve all containers, including files
        query = {'_id': {'$in': list(ids)}}

        # Exclude a few larger fields by projection - everything else will be removed later
        projection = {'permissions': 0, 'parents': 0, 'collections': 0}

        storage = cs_factory(container_type)
        containers = {}
        for container in storage.dbc.find(query, projection):
            # Filter deleted files
            storage.filter_container_files(container)

            # Add container (by string id)
            containers[container['_id']] = container

        self._containers[container_type] = containers

    def _open_file(self, target):
        """Open the given download 'file' target"""
        # TODO: For now, this is an optimization - directly accessing the signed url
        # can speed up transfer. Shouldn't open for reading basically do this?
        signed_url = None

        final_storage = get_provider(target.provider_id)
        if final_storage.storage_plugin.is_signed_url():
            try:
                signed_url = final_storage.storage_plugin.get_signed_url(target.file_id, target.src_path)
            except fs.errors.ResourceNotFound as err:
                # we might get a 404 getting the signed url, contract states we need to return OSError
                raise OSError(str(err))
            except flywheel_common.errors.ResourceNotFound as err:
                raise OSError(str(err))
        try:
            if signed_url:
                result = io.URLFileWrapper(signed_url, self._http)
                result.open()
                return result
            else:
                return final_storage.storage_plugin.open(target.file_id, target.src_path, 'rb')
        except (fs.errors.ResourceNotFound,
                fs.errors.OperationFailed,
                IOError) as err:
            # Contract is to raise an OSError if we cannot open the file
            raise OSError(str(err))

    def _open_metadata_sidecar(self, target):
        """Open the given download 'metadata file' target"""
        container = self._find_target_container(target)
        if not container:
            raise OSError('Could not resolve target {}={}, filename={}'.format(
                target.container_type, target.container_id, target.filename))

        # Convert metadata to JSON
        container = copy.deepcopy(container)
        for key in METADATA_BLACKLIST:
            if key in container:
                del container[key]
        data = json.dumps(container, indent=2, default=custom_json_serializer)

        # Set the target size at open time
        target.size = len(data)

        # And return a file-like object
        return cStringIO.StringIO(data)

    def _find_target_container(self, target):
        """Find target container or file_entry based on download target"""
        container = self._containers[target.container_type].get(target.container_id)
        if not container:
            return None

        # Determine files attribute
        files_attr = 'inputs' if target.file_group == 'input' else 'files'

        # Prefer file_id, if present
        if target.file_id:
            for file_entry in container.get(files_attr, []):
                if file_entry.get('_id') == target.file_id:
                    return file_entry
            return None

        # Otherwise, fallback on file name
        if target.filename:
            for file_entry in container.get(files_attr, []):
                if file_entry['name'] == target.filename:
                    return file_entry
            return None

        # Not a file, return the container
        return container
