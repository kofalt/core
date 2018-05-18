import itertools

from ..web.errors import InputValidationException
from ..dao import containerutil
from .column_aliases import ColumnAliases
from . import safe_eval

# TODO: Add subject once formalized
VIEW_CONTAINERS = [ 'project', 'session', 'acquisition' ]
COLUMN_CONTAINERS = [ 'project', 'session', 'acquisition', 'analysis', 'file' ]

COLUMN_BLACKLIST = [ 'permissions', 'files' ]

class ColumnSpec(object):
    """Represents a single column configured for extraction"""
    def __init__(self, container, src, dst, datatype=None, expr=None):
        # The container that this column should be extracted from
        self.container = container
        # The source path of the column value
        self.src = src
        # The destination name
        self.dst = dst
        # The optional datatype to extract
        self.datatype = datatype
        # The optional expression to apply
        self.expr = expr

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

    def validate(self):
        """Validate the configuration"""
        # Ensure that column lists have been initialized
        self.initialize_columns()

        # Verify that no blacklisted columns were added
        for col in self.columns:
            key = col.src.split('.')[0]
            if key in COLUMN_BLACKLIST:
                raise InputValidationException('Unable to select column: {}'.format(key))

    def initialize_columns(self):
        """Initializes the columns and container fields from the fetch spec, if not already initialized"""
        if not self.containers:
            self.determine_fetch_containers()
            self.add_default_columns()
            self.compile_expressions()

    def compile_expressions(self):
        """Pre-compile and validate column evaluation expressions"""
        for col in self.columns:
            # Compile the expression, if there is one
            if col.expr:
                try:
                    col.expr = safe_eval.compile_expr(col.expr, {'x'})
                except ValueError:
                    raise InputValidationException('Invalid expression: {}'.format(col.expr))

    def determine_fetch_containers(self):
        """Determine how deep we need to fetch based on columns and file specs"""
        columns = self.desc.get('columns', [])

        max_idx = -1 
        for col in columns:
            dst = col.get('dst', col['src'])
            datatype = col.get('type')
            expr = col.get('expr')

            container = self.resolve_and_add_column(col['src'], dst, datatype=datatype, expr=expr)

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

    def resolve_and_add_column(self, src, dst, datatype=None, expr=None, idx=None):
        """Resolve a column by name and add it to the various internal maps

        Arguments:
            src (str): The source key of the column value in container
            dst (str): The destination key for the column value
            datatype (str): The optional column data type
            expr (str): The optional expression to apply
            idx (int): The index where the column should be inserted

        Returns:
            str: The container name
        """
        # Lookup src alias
        src, resolved_datatype, resolved_expr = ColumnAliases.get_column_alias(src)

        if datatype is None:
            datatype = resolved_datatype

        if expr is None:
            expr = resolved_expr

        try:
            container, field = src.split('.', 1)
        except ValueError:
            raise InputValidationException('Unknown column alias: {}'.format(src))

        if container == 'subject':
            container = 'session'
            field = src
        elif container not in COLUMN_CONTAINERS:
            raise InputValidationException('Unknown container for column: {}'.format(src))

        self.add_column(container, field, dst, datatype=datatype, expr=expr, idx=idx)
        return container

    def add_column(self, container, src, dst, datatype=None, expr=None, idx=None):
        """Add a column to the various internal maps

        Arguments:
            container (str): The source container of the column value
            src (str): The source key of the column value in container
            dst (str): The destination key for the column value
            datatype (str): The optional column data type
            expr (str): The optional expression to apply
        """
        if idx is None:
            idx = len(self.columns)

        col = ColumnSpec(container, src, dst, datatype=datatype, expr=expr)
        self.columns.insert(idx, col)
        if container not in self.column_map:
            self.column_map[container] = []
        self.column_map[container].append(col)
        self.flat_columns.insert(idx, dst)

