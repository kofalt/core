"""Provide hierarchy-walking based download strategy"""
from ... import files

from .. import models
from .container_path_resolver import ContainerPathResolver
from .hierarchy import HierarchyDownloadStrategy

class FullDownloadStrategy(HierarchyDownloadStrategy):
    """Full download strategy, places files in a folder structure as follows:

    proj_label
    |-- proj_label.flywheel.json
    |-- ANALYSES
    |   |-- ana_label
    |       |-- ana_label.flywheel.json
    |       |-- INPUT
    |       |-- OUTPUT
    |-- FILES
    |   |-- filename.ext
    |   |-- filename.ext.flywheel.io
    |-- SUBJECTS
        |-- subj_label
            |-- subj_label.flywheel.json
            |-- ANALYSES
            |-- FILES
            |-- SESSIONS
                |-- sess_label
                    |-- sess_label.flywheel.json
                    |-- ANALYSES
                    |-- FILES
                    |-- ACQUISITIONS
                        |-- acq_label
                            |-- acq_label.flywheel.json
                            |-- FILES
    """

    # Include parents
    include_parents = True

    default_archive_prefix = 'flywheel'

    def __init__(self, log, params):
        super(FullDownloadStrategy, self).__init__(log, params)

        self.include_analyses = bool(params.get('analyses', False))
        self.include_metadata = bool(params.get('metadata', False))
        self.require_info = self.include_metadata  # Whether or not we need retrieve metadata

        # New style path resolution
        self._resolver = ContainerPathResolver(path_prefix=self.archive_prefix,
            include_group=False, prefix_containers=True)

    def identify_targets(self, spec, uid, summary):
        # Normalize input for summary
        if summary:
            spec = { 'nodes': spec }
        return super(FullDownloadStrategy, self).identify_targets(spec, uid, summary)

    def visit_container(self, parents, container_type, container, summary):
        if summary or not self.include_metadata:
            return []

        # Produce metadata in the actual download case
        container_id = container['_id']
        container_path = self._resolver.get_path(parents, container_type, container_id)
        metadata_target = self._create_metadata_target(container_path, container_type,
            container_id, container)

        return [metadata_target]

    def visit_file(self, parents, parent_type, file_group, file_entry, summary):
        if summary:
            parent = {}
            parent_id = None
        else:
            parent = parents[parent_type]
            parent_id = parent['_id']

        # Produce the file path
        src_path = files.get_file_path(file_entry)
        metadata_target = None

        if src_path:  # silently skip missing files
            file_id=file_entry.get('_id')
            filename=file_entry['name']

            if summary:
                dst_path = ''  # path not required for summary
            else:
                # Container path + filename
                container_path = self._resolver.get_path(parents, parent_type, parent_id)

                # Include capitalized file group for analyses
                if parent_type == 'analysis':
                    container_path += (file_group.upper(),)
                else:
                    container_path += ('FILES',)

                file_path = container_path + (file_entry['name'],)

                if self.include_metadata:
                    # Create metadata target
                    metadata_target = self._create_metadata_target(file_path, parent_type,
                        parent_id, file_entry, file_id=file_id, filename=filename,
                        file_group=file_group, provider_id=file_entry['provider_id'])

                dst_path =  '/'.join(file_path)

            result = [
                models.DownloadTarget('file', dst_path, parent_type, parent_id, file_entry['modified'],
                    file_entry['size'], file_entry.get('type'), file_entry['provider_id'], file_id=file_id, filename=filename,
                    file_group=file_group, src_path=src_path)
            ]

            # Add metadata target
            if metadata_target:
                result.append(metadata_target)

            return result
        else:
            self.log.debug('Could not resolve path for file {} on {} {}. File will be skipped in download.'.format(file_entry['name'], parent_type, parent_id))
            return []

    def _create_metadata_target(self, path, parent_type, parent_id, container, file_id=None,
            filename=None, file_group=None, provider_id=None):
        metadata_name = '{}.flywheel.json'.format(path[-1])

        if filename is not None:
            # Co-located if file
            path = path[:-1] + (metadata_name,)
        else:
            # Otherwise located inside the directory if container
            path += (metadata_name,)

        dst_path = '/'.join(path)

        # NOTE: We always return size=0 for metadata - it will be set just-in-time
        return models.DownloadTarget('metadata_sidecar', dst_path, parent_type, parent_id,
            container['modified'], 0, None, provider_id, file_id=file_id, filename=filename,
            file_group=file_group)
