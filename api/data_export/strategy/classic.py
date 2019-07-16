"""Provide hierarchy-walking based download strategy"""
from ... import files

from .. import models
from .container_path_resolver import ContainerPathResolver
from .hierarchy import HierarchyDownloadStrategy

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

        self._resolver = ContainerPathResolver(path_prefix=self.archive_prefix)

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
        if summary:
            parent = {}
            parent_id = None
        else:
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
                # Container path + filename
                container_path = self._resolver.get_path(parents, parent_type, parent_id)
                dst_path =  '/'.join(container_path + (file_entry['name'],))

            return [
                models.DownloadTarget('file', dst_path, parent_type, parent_id, file_entry['modified'],
                    file_entry['size'], file_entry.get('type'), file_entry['provider_id'], file_id=file_entry.get('_id'),
                    filename=file_entry['name'], file_group=file_group, src_path=src_path)
            ]
        else:
            self.log.debug('Could not resolve path for file {} on {} {}. File will be skipped in download.'.format(file_entry['name'], parent_type, parent_id))
            return []

    def create_archive_filename(self):
        # Legacy behavior, return analysis_label.tar as the filename for single analysis targets
        if self._is_analysis and self._analysis_label:
            return 'analysis_{}.tar'.format(self._analysis_label)
        return super(ClassicDownloadStrategy, self).create_archive_filename()
