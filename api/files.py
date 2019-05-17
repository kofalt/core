import os
import cgi
import json
import six
import hashlib
import uuid
import datetime

import fs.move
import fs.tempfs
import fs.path
import fs.errors

from flywheel_common import storage

from . import config, util

DEFAULT_HASH_ALG = "sha384"


class FileProcessor(object):
    def __init__(self, persistent_fs):
        """
        File processing service layer object. Handles all file IO

        :param self: self reference
        :Storage persistent_fs: storage layer supported by flywheel storage class

        """
        self._persistent_fs = persistent_fs

    def create_new_file(self, filename, **kwargs):
        """ Create a new block storage file with a unique uuid opened for writing

        :param self: self reference
        :param string filename: filename for the new file
        :param kwargs: Additional args to pass to open
        :rtype FileHasherWriter: Returns the special wrapper so extend that interface as needed

        """
        new_uuid = str(uuid.uuid4())
        if not filename:
            filename = new_uuid

        path = util.path_from_uuid(new_uuid)

        fileobj = self._persistent_fs.open(new_uuid, path, "wb", **kwargs)
        fileobj.filename = filename

        return path, FileHasherWriter(fileobj)

    def process_form(self, request, use_filepath=False, tempdir_name=None):
        """
        Some workarounds to make webapp2 process forms in an intelligent way.
        Normally webapp2/WebOb Reqest.POST would copy the entire request stream
        into a single file on disk.
        https://github.com/Pylons/webob/blob/cb9c0b4f51542a7d0ed5cc5bf0a73f528afbe03e/webob/request.py#L787
        https://github.com/moraes/webapp-improved/pull/12
        We pass request.body_file (wrapped wsgi input stream)
        to our custom subclass of cgi.FieldStorage to write each upload file
        to a separate file on disk, as it comes in off the network stream from the client.
        Then we can rename these files to their final destination,
        without copying the data gain.

        Returns (tuple):
            form: SingleFileFieldStorage instance
            tempdir: tempdir the file was stored in.

        Keep tempdir in scope until you don't need it anymore; it will be deleted on GC.
        """

        # If chunked encoding, indicate that the input will be terminated via EOF
        # before getting the request body
        if request.headers.get("Transfer-Encoding", None) == "chunked":
            request.environ["wsgi.input_terminated"] = True

        # Copied from WebOb source:
        # https://github.com/Pylons/webob/blob/cb9c0b4f51542a7d0ed5cc5bf0a73f528afbe03e/webob/request.py#L790
        env = request.environ.copy()
        env.setdefault("CONTENT_LENGTH", "0")
        env["QUERY_STRING"] = ""

        # We only use the tempdir_name for Token and Placer strategy
        if tempdir_name:
            if not config.local_fs.get_fs().exists(tempdir_name):
                config.local_fs.get_fs().makedirs(tempdir_name)
            field_storage_class = get_single_file_field_storage(config.local_fs, use_filepath=use_filepath, tempdir_name=tempdir_name)
        else:
            field_storage_class = get_single_file_field_storage(self._persistent_fs, use_filepath=use_filepath)

        form = field_storage_class(fp=request.body_file, environ=env, keep_blank_values=True)

        form.file = FileHasherWriter(form.file)

        return form

    def create_file_fields(self, filename, filepath, size, hash_, uuid_=None, mimetype=None, modified=None):
        """
        Creates a standard object with the required fields for processing via placers.
        This will be replaced with a standardized file model in the future
        """
        if not modified:
            modified = datetime.datetime.utcnow()
        if not mimetype:
            mimetype = util.guess_mimetype(filename)

        return util.obj_from_map({"uuid": uuid_, "filename": filename, "path": filepath, "filepath": filepath, "size": size, "hash": hash_, "mimetype": mimetype, "modified": modified})  # Some placers use path others use filepath

    @property
    def persistent_fs(self):
        return self._persistent_fs

    def __exit__(self, exc, value, tb):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        # Cleaning up
        # We need to keep storage because files will live there between requests
        # We will require the placer to clean up files as needed when the request flows are finished
        pass


class FileHasherWriter(object):
    """File wrapper that hashes while writing to a file

        This file will not be needed with native cloud object storage but will be good to use for local
        storage files.  Once we have assigned each file to provider type then we can return this special
        object only for local files and normal file objects in all other cases

    """

    def __init__(self, fileobj, hash_alg=None):
        """Create a new file hasher/writer

        Arguments:
            fileobj (file): The wrapped file object
            hash_alg (str): The hash algorithm, or None to use default
        """
        self.fileobj = fileobj
        self.hash_alg = hash_alg or DEFAULT_HASH_ALG
        self.hasher = hashlib.new(self.hash_alg)
        self.size = 0

    @property
    def hash(self):
        """Return the formatted hash of the file"""
        return storage.format_hash(self.hash_alg, self.hasher.hexdigest())

    @property
    def filename(self):
        return self.fileobj.filename

    @filename.setter
    def filename(self, filename):
        self.fileobj.filename = filename

    @property
    def filepath(self):
        return self.fileobj.filepath

    @property
    def path(self):
        return self.fileobj.path

    @path.setter
    def path(self, path):
        self.fileobj.path = path

    def write(self, data):
        self.fileobj.write(data)
        self.hasher.update(data)
        self.size += len(data)

    def close(self):
        self.fileobj.close()


def get_single_file_field_storage(file_system, use_filepath=False, tempdir_name=False):
    # pylint: disable=attribute-defined-outside-init

    # We dynamically create this class because we
    # can't add arguments to __init__.
    # This is due to the FieldStorage we create
    # in turn creating a FieldStorage for different
    # parts of the form, with a hardcoded set of args
    # https://github.com/python/cpython/blob/1e3e162ff5c0cc656559c43914439ab3e5734f00/Lib/cgi.py#L696
    # https://github.com/python/cpython/blob/1e3e162ff5c0cc656559c43914439ab3e5734f00/Lib/cgi.py#L728

    class SingleFileFieldStorage(cgi.FieldStorage):

        bufsize = 2 ** 20

        def __init__(self, *args, **kwargs):

            self._uuid = str(uuid.uuid4())

            cgi.FieldStorage.__init__(self, *args, **kwargs)

        @property
        def uuid(self):
            return self._uuid

        def make_file(self, binary=None):

            self.hasher = hashlib.new(DEFAULT_HASH_ALG)
            # Sanitize form's filename (read: prevent malicious escapes, bad characters, etc)
            # dont overwrite filename so we have it easily for metadata
            # TODO: This should be abstracted out so that its the same method used in in process_upload when no files are added but metadata is given, as it is in here
            if use_filepath:
                self.filename = util.sanitize_path(self.filename)
            else:
                self.filename = os.path.basename(self.filename)

            # move this to a utility function and use it in both places.
            # It needs to be changed in the placers that assume temp dir locations, only PackFile that I am aware of
            if tempdir_name:
                # If using the tempdir we assume we are going to pack them up with the original filenames
                self.filepath = tempdir_name + "/" + self.filename
            else:
                self.filepath = util.path_from_uuid(self._uuid)

            # Some placers reference path and others filepath so we use both to make it work for now
            self.path = self.filepath

            if not isinstance(self.filepath, unicode):
                self.filepath = six.u(self.filepath)

            self.open_file = file_system.open(self._uuid, self.filepath, "wb")

            return self.open_file

        # override private method __write of superclass FieldStorage
        # _FieldStorage__file is the private variable __file of the same class
        def _FieldStorage__write(self, line):
            # pylint: disable=access-member-before-definition
            if self._FieldStorage__file is not None:
                # Always write fields of type "file" to disk for consistent renaming behavior
                if self.filename:
                    self.file = self.make_file("")
                    self.file.write(self._FieldStorage__file.getvalue())
                    self.hasher.update(self._FieldStorage__file.getvalue())
                self._FieldStorage__file = None

            self.file.write(line)

            # NOTE: In case of metadata, we don't have a file name and we also don't have a hasher,
            # so skipping the hasher.update
            if self.filename:
                self.hasher.update(line)

    return SingleFileFieldStorage


# File extension --> scitran file type detection hueristics.
# Listed in precendence order.
with open(os.path.join(os.path.dirname(__file__), "filetypes.json")) as fd:
    TYPE_MAP = json.load(fd)

KNOWN_FILETYPES = {ext: filetype for filetype, extensions in TYPE_MAP.iteritems() for ext in extensions}


def guess_type_from_filename(filename):
    particles = filename.split(".")[1:]
    extentions = ["." + ".".join(particles[i:]) for i in range(len(particles))]
    for ext in extentions:
        filetype = KNOWN_FILETYPES.get(ext.lower())
        if filetype:
            break
    else:
        filetype = None
    return filetype


def get_valid_file(file_info):
    """
    Get the file path and the filesystem where the file exists.

    First try to serve the file from the current filesystem and
    if the file is not found (likely has not migrated yet) and the instance
    still supports the legacy storage, attempt to serve from there.

    :param file_info: dict, contains the _id and the hash of the file
    :return: (<file's path>, <filesystem>)
    """

    file_id = file_info.get("_id", "")
    file_path = get_file_path(file_info)
    return file_path, get_fs_by_file_path(file_id, file_path)


def get_file_path(file_info):
    """
    Get the file path. If the file has id then returns path_from_uuid otherwise path_from_hash.

    :param file_info: dict, contains the _id and the hash of the file
    :return: <file's path>
    """
    file_id = file_info.get("_id", "")
    file_hash = file_info.get("hash", "")
    file_uuid_path = None
    file_hash_path = None

    if file_hash:
        file_hash_path = util.path_from_hash(file_hash)

    if file_id:
        file_uuid_path = util.path_from_uuid(file_id)

    file_path = file_uuid_path or file_hash_path
    return file_path


def get_fs_by_file_path(file_id, file_path):
    """
    @deprecated
    This method is only intended to support the pyfs storage class.
    Once new storage classes are implemented this should be moved into the specific file attributes

    Get the filesystem where the file exists by a valid file path.
    Attempt to serve file from current storage in config.

    If file is not found (likely has not migrated yet) and the instance
    still supports the legacy storage, attempt to serve from there.
    """

    # When we add more native storage types we will have to store the file system type in the file object and
    # not rely on this method to determine where its physically located
    if config.primary_storage.get_file_info(file_id, file_path):
        return config.primary_storage

    elif config.support_legacy_fs and config.local_fs.get_file_info(file_id, file_path):
        return config.local_fs

    ### Temp fix for 3-way split storages, see api.config.local_fs2 for details
    elif config.support_legacy_fs and config.local_fs2 and config.local_fs2.get_file_info(file_id, file_path):
        return config.local_fs2
    ###

    else:
        raise fs.errors.ResourceNotFound("File not found: %s" % file_path)
