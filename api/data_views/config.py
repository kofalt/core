import itertools

from ..web.errors import InputValidationException
from ..dao import containerutil

# TODO: Add subject once formalized
VIEW_CONTAINERS = [ 'project', 'session', 'acquisition' ]
COLUMN_CONTAINERS = [ 'project', 'session', 'acquisition', 'analysis', 'file' ]


class ColumnSpec(object):
    """Represents a single column configured for extraction"""
    def __init__(self, container, src, dst, datatype=None):
        # The container that this column should be extracted from
        self.container = container
        # The source path of the column value
        self.src = src
        # The destination name
        self.dst = dst
        # The optional datatype to extract
        self.datatype = datatype

class DataViewConfig(object):
    """Contains all relevant configuration for executing a DataView"""
    def __init__(self, desc):
        # The original data view description
        self.desc = desc

        # The original file spec, if there was one
        self.file_spec = desc.get('fileSpec', None)

        # The file container, or None
        self.file_container = None

        # The analysis filter, if present in the file_spec
        self.analysis_filter = None

        # Parse out the file spec options
        if self.file_spec:
            self.file_container = containerutil.singularize(self.file_spec['container'])
            self.analysis_filter = self.file_spec.get('analysisFilter')

        # The set of columns
        self.columns = []

        # A map of container to columns for that container that includes column indexes
        self.column_map = {}

        # The ordered set of columns
        self.flat_columns = []

        # The list of containers that will be queried as part of the pipeline
        self.containers = []

    def get_file_match_type(self):
        if self.file_spec:
            return self.file_spec.get('match', 'first')
        return 'first'

    def initialize_columns(self):
        """Initializes the columns and container fields from the fetch spec"""
        self.determine_fetch_containers()
        self.add_default_columns()

    def determine_fetch_containers(self):
        """Determine how deep we need to fetch based on columns and file specs"""
        columns = self.desc['columns']

        max_idx = -1 
        for col in columns:
            src = col['src']
            dst = col.get('dst', src)
            datatype = col.get('type')
            container, field = src.split('.', 1)

            if container == 'subject':
                container = 'session'
                field = src
            elif container not in COLUMN_CONTAINERS:
                raise InputValidationException('Unknown container for column: {}'.format(src))

            self.add_column(container, field, dst, datatype)
            if container in VIEW_CONTAINERS:
                max_idx = max(max_idx, VIEW_CONTAINERS.index(container))

        # Check file spec container as well
        if self.file_container:
            if self.file_container not in VIEW_CONTAINERS:
                raise InputValidationException('Unexpected file container: {}'.format(self.file_spec['container']))

            file_idx = VIEW_CONTAINERS.index(self.file_container)
            # If there are columns specified below the file_container, that's an error
            if file_idx < max_idx:
                raise InputValidationException('File match must be the lowest container on the hierarchy')
            max_idx = max(max_idx, file_idx)

        assert max_idx > -1
        self.containers = VIEW_CONTAINERS[:max_idx+1]

    def add_default_columns(self):
        """Get all columns including auto generated id and label columns"""
        include_ids = self.desc.get('includeIds', True)
        include_labels = self.desc.get('includeLabels', True)

        idx = itertools.count()

        for cont in self.containers:
            if cont == 'session':
                # TODO: Remove once subjects are formalized
                if include_ids:
                    self.add_column( 'session', 'subject._id', 'subject', idx=next(idx) )
                if include_labels:
                    self.add_column( 'session', 'subject.code', 'subject_label', idx=next(idx) )

            if include_ids:
                self.add_column( cont, '_id', cont, idx=next(idx) )

            if include_labels:
                self.add_column(cont, 'label', '{}_label'.format(cont), idx=next(idx) )

    def add_column(self, container, src, dst, datatype=None, idx=None):
        """Add a column to the various internal maps

        Arguments:
            container (str): The source container of the column value
            src (str): The source key of the column value in container
            dst (str): The destination key for the column value
            datatype (str): The optional column data type
        """
        if idx is None:
            idx = len(self.columns)

        col = ColumnSpec(container, src, dst, datatype)
        self.columns.insert(idx, col)
        if container not in self.column_map:
            self.column_map[container] = []
        self.column_map[container].append(col)
        self.flat_columns.insert(idx, dst)

