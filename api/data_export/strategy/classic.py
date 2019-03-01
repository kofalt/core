"""Provide hierarchy-walking based download strategy"""
import pytz

from ... import util, files

from .. import models
from .hierarchy import HierarchyDownloadStrategy

def _get_parent_type_list(container_type):
    """Get the top-down list of parents, including container_type"""
    containers = ['group', 'project', 'subject', 'session', 'acquisition']
    idx = containers.index(container_type)
    return containers[0:idx+1]

class ClassicDownloadStrategy(HierarchyDownloadStrategy):
    """Classic download strategy, places files in the traditional folder structure as follows:
        - {prefix}
        - {group id}
        - {project label}
        - {subject code}
        - {session label | timestamp | uid }
        - {acquisition label | timestamp | uid }

        - {analysis label}
            - input/
            - output/

    With the exception of analyses files are stored directly under each container, with no metadata.
    For analyses, files are stored in inputs and outputs subfolders.
    """
    default_archive_prefix = 'scitran'
    include_analyses = False

    def __init__(self, log, params):
        super(ClassicDownloadStrategy, self).__init__(log, params)

        # Cache for container id -> path tuple
        self._container_path_map = {}

        # Cache for used path tuples
        self._used_paths = set()

        # Whether or not this is an analysis download
        self._is_analysis = False

        # Store last seen analysis label
        self._analysis_label = None

    def identify_targets(self, spec, uid, summary):
        # Normalize input for summary
        if summary:
            spec = { 'nodes': spec }

        nodes = spec.get('nodes', [])

        # Override to detect if this is a single analysis retrieval
        if len(nodes) == 1 and nodes[0]['level'] == 'analysis':
            self._is_analysis = True

        return super(ClassicDownloadStrategy, self).identify_targets(spec, uid, summary)

    def visit_file(self, parents, parent_type, file_group, file_entry, summary):
        # Produce the file path
        parent = parents[parent_type]
        parent_id = parent['_id']

        if parent_type == 'analysis':
            self._analysis_label = parent.get('label')

        src_path = files.get_file_path(file_entry)
        if src_path:  # silently skip missing files
            if summary:
                dst_path = ''  # path not required for summary
            elif self._is_analysis:
                # Single analysis target, simply join the file_group
                dst_path = '{}/{}/{}'.format(parent.get('label', 'unknown_analysis'),
                    file_group, file_entry['name'])
            else:
                dst_path = self._get_path(parents, parent_type, parent_id, file_entry)

            return [
                models.DownloadTarget('file', dst_path, parent_type, parent_id, file_entry['modified'],
                    file_entry['size'], file_entry.get('type'), src_path=src_path, file_hash=file_entry.get('hash'), file_id=file_entry.get('_id'))
            ]
        else:
            self.log.debug('Could not resolve path for file {} on {} {}. File will be skipped in download.'.format(file_entry['name'], parent_type, parent_id))

    def create_archive_filename(self):
        # Legacy behavior, return analysis_label.tar as the filename for single analysis targets
        if self._is_analysis and self._analysis_label:
            return 'analysis_{}.tar'.format(self._analysis_label)
        return super(ClassicDownloadStrategy, self).create_archive_filename()

    def _get_path(self, parents, parent_type, parent_id, file_entry):
        """Get the full destination path for the given file"""
        # Resolve the container path
        path = self._container_path_map.get(parent_id)
        if not path:
            path = (self.archive_prefix, )

            # Normal container hierarchy
            for container_type in _get_parent_type_list(parent_type):
                path = self._add_path_component(path, container_type, parents)

        # Add the filename to the path
        path = path + (file_entry['name'],)
        return '/'.join(path)

    def _add_path_component(self, prefix, parent_type, parents):
        """Add the path component for the given parent_type to prefix"""
        parent = parents.get(parent_type)
        parent_id = parent.get('_id') if parent else None

        if parent_id is None:
            return prefix + ('unknown',)

        # Cached lookup
        path = self._container_path_map.get(parent_id)
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
            part = 'unknown_{}'.format(parent_type)

        # Ensure a unique value for this container
        path = prefix + (part,)
        suffix = 0
        while path in self._used_paths:
            path = prefix + ('{}_{}'.format(part, suffix), )
            suffix += 1

        # Populate cache
        self._used_paths.add(path)
        self._container_path_map[parent_id] = path

        return path
