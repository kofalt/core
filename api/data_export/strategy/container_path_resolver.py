"""Provides tool for creating file paths for containers"""
import pytz

from ... import util


CONTAINERS = ['group', 'project', 'subject', 'session', 'acquisition']
CONTAINERS_WITHOUT_GROUP = ['project', 'subject', 'session', 'acquisition']

CONTAINER_FOLDERS = {
    'subject': 'SUBJECTS',
    'session': 'SESSIONS',
    'acquisition': 'ACQUISITIONS',
    'analysis': 'ANALYSES',
    'files': 'FILES'
}


def _get_parent_type_list(container_type, include_group):
    """Get the top-down list of parents, including container_type"""
    containers = CONTAINERS if include_group else CONTAINERS_WITHOUT_GROUP
    idx = containers.index(container_type)
    return containers[0:idx+1]


class ContainerPathResolver(object):
    """Class that resolves containers to a unique folder path, per unique container"""

    def __init__(self, path_prefix=None, prefix_containers=False, include_group=True):
        """Create a ContainerPathResolver.

        Args:
            path_prefix (tuple|str): The optional path prefix
            prefix_containers (bool): Whether or not to add a prefix for each container.
                For example: SUBJECTS/{subject_label}/SESSIONS/{session_label}
            include_group (bool): Whether or not to include the group path
        """
        # Cache for container id -> path tuple
        self._container_path_map = {}

        # Cache for used path tuples
        self._used_paths = set()

        if path_prefix is not None:
            if isinstance(path_prefix, (str, unicode)):
                self._prefix = (path_prefix,)
            else:
                self._prefix = path_prefix
        else:
            self._prefix = ()

        self._prefix_containers = prefix_containers
        self._include_group = include_group

    def get_path(self, parents, container_type, container_id):
        """Get the full destination path for the given container

        Args:
            parents (dict): The dictionary of containers, by type
            container_type (str): The type of container to resolve
            container_id (str): The container id

        Returns:
            tuple: A tuple of path components, including a prefix
        """
        # Resolve the container path
        path = self._container_path_map.get(container_id)
        if not path:
            # Start with prefix
            path = self._prefix

            # If this is an analysis, resolve the parents first
            is_analysis = container_type == 'analysis'
            if is_analysis:
                container_type = parents['analysis']['parent']['type']

            # Normal container hierarchy
            for container_type in _get_parent_type_list(container_type, self._include_group):
                path = self._add_path_component(path, container_type, parents)

            if is_analysis:
                # Add final analysis path
                path = self._add_path_component(path, 'analysis', parents)

        return path

    def _add_path_component(self, prefix, container_type, parents):
        """Add the path component for the given container_type to prefix"""
        parent = parents.get(container_type)
        container_id = parent.get('_id') if parent else None

        # Add folder prefixes, if specified
        if self._prefix_containers:
            folder_name = CONTAINER_FOLDERS.get(container_type)
            if folder_name is not None:
                prefix = prefix + (folder_name,)

        if container_id is None:
            return prefix + ('unknown',)

        # Cached lookup
        path = self._container_path_map.get(container_id)
        if path:
            return path

        # Otherwise resolve a unique component
        part = ''
        if not part and parent.get('label'):
            part = util.sanitize_string_to_filename(parent['label'])
        if not part and parent.get('timestamp'):
            timezone = parent.get('timezone')
            if timezone:
                part = pytz.timezone('UTC').localize(parent['timestamp']).astimezone(pytz.timezone(timezone)).strftime('%Y%m%d_%H%M')
            else:
                part = parent['timestamp'].strftime('%Y%m%d_%H%M')
        if not part and parent.get('uid'):
            part = parent['uid']
        if not part and parent.get('code'):
            part = parent['code']

        if part:
            part = part.encode('ascii', errors='ignore')
        else:
            part = 'unknown_{}'.format(container_type)

        # Ensure a unique value for this container
        path = prefix + (part,)
        suffix = 0
        while path in self._used_paths:
            path = prefix + ('{}_{}'.format(part, suffix), )
            suffix += 1

        # Populate cache
        self._used_paths.add(path)
        self._container_path_map[container_id] = path

        return path
