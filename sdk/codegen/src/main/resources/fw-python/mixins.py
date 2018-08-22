import collections

def params_to_dict(method_name, args, kwargs):
    """Given args and kwargs, return a dictionary object"""
    if len(args) > 1:
        raise TypeError(method_name + '() takes at most 1 positional argument')
    if args:
        if not isinstance(args[0], collections.MutableMapping):
            raise ValueError(method_name + '() expects first argument to be a dictionary')
        elif kwargs:
            raise ValueError(method_name + '() expects either a dictionary or kwargs')
        return args[0]
    elif not kwargs:
        raise ValueError(method_name + '() expects either a dictionary or kwargs')
    return kwargs

def params_to_list(args):
    """Convert a list of arguments (some of which may be lists) to a flat list"""
    result = []
    for arg in args:
        if isinstance(arg, list):
            result += arg
        else:
            result.append(arg)
    return result

class ContainerBase(object):
    def __init__(self):
        self.__context = None
        self.__files_updated = False

    def _set_context(self, context):
        """Set the context object (i.e. flywheel client instance)"""
        self.__context = context

    def _invoke_container_api(self, fmt, *args, **kwargs):
        """Invoke container api, formatting the string first"""
        if self.__context:
            fname = fmt.format(self.container_type)
            fn = getattr(self.__context, fname, None)
            if fn:
                return fn(*args, **kwargs)
        return None

    def update(self, *args, **kwargs):
        """Update container using dictionary or kwargs"""
        # Could either pass a dictionary or kwargs values
        body = params_to_dict('update', args, kwargs)

        # Update the container
        return self._invoke_container_api('modify_{}', self.id, body)

    def reload(self):
        """Reload the object from the server, and return the result"""
        return self._invoke_container_api('get_{}', self.id)

    def __update_files(self):
        """Update the _parent attribute for each file"""
        if self.__files_updated:
            return

        files = getattr(self, '_files', None)
        for entry in files:
            setattr(entry, '_parent', self)

        self.__files_updated = True

    def __getattribute__(self, name):
        # Handle lazy load and update of files
        if name == 'files' and self.id is not None:
            if self._files is None:
                obj = self._invoke_container_api('get_{}', self.id)
                self._files = getattr(obj, '_files', None)
                if self._files is None:
                    self._files = []
                self.__files_updated = False

            self.__update_files()

        return object.__getattribute__(self, name)

    def __getattr__(self, name):
        # Lazily load children
        if name in self.child_types and self.id is not None:
            prop_name = '_{}'.format(name)
            result = getattr(self, prop_name, None)
            if result is None:
                # e.g. get_project_sessions
                fname = 'get_{}_{}'.format(self.container_type, name)
                fn = getattr(self.__context, fname, None)

                if not fn:
                    raise ValueError('Unknown child type for {}: {}'.format(self.container_type, name))

                result = fn(self.id)
                if result is None:
                    result = []

                setattr(self, prop_name, result)
            return result

        return getattr(object, name)

class InfoMethods(object):
    def replace_info(self, info):
        """Fully replace this object's info with the provided value"""
        return self._invoke_container_api('replace_{}_info', self.id, info)

    def update_info(self, *args, **kwargs):
        """Update the info with the passed in arguments"""
        # Could either pass a dictionary or kwargs values
        body = params_to_dict('update_info', args, kwargs)
        return self._invoke_container_api('set_{}_info', self.id, body)

    def delete_info(self, *args):
        """Delete the info fields listed in args"""
        body = params_to_list(args)
        return self._invoke_container_api('delete_{}_info_fields', self.id, body)


class TagMethods(object):
    def add_tag(self, tag):
        """Add the given tag to the object"""
        return self._invoke_container_api('add_{}_tag', self.id, tag)

    def rename_tag(self, tag, new_tag):
        """Rename tag on object"""
        return self._invoke_container_api('rename_{}_tag', self.id, tag, new_tag)

    def delete_tag(self, tag):
        """Delete tag from object"""
        return self._invoke_container_api('delete_{}_tag', self.id, tag)


class NoteMethods(object):
    def add_note(self, message):
        """Add the given note to the object"""
        return self._invoke_container_api('add_{}_note', self.id, message)

    def delete_note(self, note_id):
        """Delete the given note on the object"""
        return self._invoke_container_api('delete_{}_note', self.id, note_id)


class PermissionMethods(object):
    def add_permission(self, permission):
        """Add a permission to a container"""
        return self._invoke_container_api('add_{}_permission', self.id, permission)

    def update_permission(self, user_id, permission):
        """Update a user's permission on container"""
        return self._invoke_container_api('modify_{}_user_permission', self.id, user_id, permission)

    def delete_permission(self, user_id):
        """Delete a user's permission from container"""
        return self._invoke_container_api('delete_{}_user_permission', self.id, user_id)


class FileMethods(object):
    def upload_file(self, file):
        """Upload a file to a container"""
        return self._invoke_container_api('upload_file_to_{}', self.id, file)

    def download_file(self, file_name, dest_file):
        """Download file to the given path"""
        return self._invoke_container_api('download_file_from_{}', self.id, file_name, dest_file)

    def get_file_download_url(self, file_name):
        """Get a ticketed download url for the file"""
        return self._invoke_container_api('get_{}_download_url', self.id, file_name)

    def read_file(self, file_name):
        """Read the contents of the file"""
        return self._invoke_container_api('download_file_from_{}_as_data', self.id, file_name)

    def update_file(self, file_name, *args, **kwargs):
        """Update a file's type and/or modality"""
        body = params_to_dict('update_file', args, kwargs)
        return self._invoke_container_api('modify_{}_file', self.id, file_name, body)

    def delete_file(self, file_name):
        """Delete file from the container"""
        return self._invoke_container_api('delete_{}_file', self.id, file_name)

    def replace_file_info(self, file_name, info):
        """Fully replace this file's info with the provided value"""
        return self._invoke_container_api('replace_{}_file_info', self.id, file_name, info)

    def update_file_info(self, file_name, *args, **kwargs):
        """Update the file's info with the passed in arguments"""
        # Could either pass a dictionary or kwargs values
        body = params_to_dict('update_file_info', args, kwargs)
        return self._invoke_container_api('set_{}_file_info', self.id, file_name, body)

    def delete_file_info(self, file_name, *args):
        """Delete the file info fields listed in args"""
        body = params_to_list(args)
        return self._invoke_container_api('delete_{}_file_info_fields', self.id, file_name, body)

    def replace_file_classification(self, file_name, classification, modality=None):
        """Fully replace a file's modality and classification"""
        body = {'replace': classification}
        if modality is not None:
            body['modality'] = modality
        return self._invoke_container_api('modify_{}_file_classification', self.id, file_name, body)

    def update_file_classification(self, file_name, classification):
        """Update a file's classification"""
        return self._invoke_container_api('set_{}_file_classification', self.id, file_name, classification)

    def delete_file_classification(self, file_name, classification):
        """Delete a file's classification fields"""
        return self._invoke_container_api('delete_{}_file_classification_fields', self.id, file_name, classification)


class GroupMixin(ContainerBase, TagMethods, PermissionMethods):
    container_type = 'group'
    child_types = ['projects']


class ProjectMixin(ContainerBase, TagMethods, NoteMethods, PermissionMethods, FileMethods, InfoMethods):
    container_type = 'project'
    child_types = ['sessions', 'analyses', 'files']


class SessionMixin(ContainerBase, TagMethods, NoteMethods, FileMethods, InfoMethods):
    container_type = 'session'
    child_types = ['acquisitions', 'analyses', 'files']


class AcquisitionMixin(ContainerBase, NoteMethods, TagMethods, FileMethods, InfoMethods):
    container_type = 'acquisition'
    child_types = ['analyses', 'files']


class AnalysisMixin(ContainerBase, NoteMethods, TagMethods, FileMethods, InfoMethods):
    container_type = 'analysis'
    child_types = ['files']


class FileMixin(ContainerBase):
    container_type = 'file'
    child_types = []

    def __init__(self):
        super(FileMixin, self).__init__()
        self._parent = None

    @property
    def parent(self):
        return self._parent

    @property
    def url(self):
        """Get a ticketed download url for the file"""
        return self._parent.get_file_download_url(self.name)

    def download(self, dest_file):
        """Download file to the given path"""
        return self._parent.download_file(self.name, dest_file)

    def read(self):
        """Read the contents of the file"""
        return self._parent.read_file(self.name)

    def replace_info(self, info):
        """Fully replace this file's info with the provided value"""
        return self._parent.replace_file_info(self.name, info)

    def update_info(self, *args, **kwargs):
        """Update the file's info with the passed in arguments"""
        return self._parent.update_file_info(self.name, *args, **kwargs)

    def delete_info(self, *args):
        """Delete the file info fields listed in args"""
        return self._parent.delete_file_info(self.name, *args)

    def update(self, *args, **kwargs):
        """Update a file's type and/or modality"""
        return self._parent.update_file(self.name, *args, **kwargs)

    def replace_classification(self, classification, modality=None):
        """Fully replace a file's modality and classification"""
        return self._parent.replace_file_classification(self.name, classification, modality=modality)

    def update_classification(self, classification):
        """Update a file's classification"""
        return self._parent.update_file_classification(self.name, classification)

    def delete_classification(self, classification):
        """Delete a file's classification fields"""
        return self._parent.delete_file_classification(self.name, classification)
