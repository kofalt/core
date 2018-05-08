from ..web.errors import InputValidationException
from ..dao import containerutil

# TODO: Add subject once formalized
VIEW_CONTAINERS = [ 'project', 'session', 'acquisition' ]
COLUMN_CONTAINERS = [ 'project', 'session', 'acquisition', 'analysis', 'file' ]

def id_column(cont_type):
    return ( cont_type, '_id', cont_type )

def label_column(cont_type):
    return ( cont_type, 'label', '{}_label'.format(cont_type) )

class DataViewConfig(object):
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

        # The list of file columns, if discovered
        self.file_columns = []
    
        # The list of containers that will be queried as part of the pipeline
        self.containers = []

    def get_file_match_type(self):
        if self.file_spec:
            return self.file_spec.get('match', 'first')
        return 'first'

    def initialize_columns(self):
        """Initializes the columns and container fields from the fetch spec"""
        self.determine_fetch_containers()
        self.format_columns()

    def determine_fetch_containers(self):
        """Determine how deep we need to fetch based on columns and file specs"""
        columns = self.desc['columns']

        max_idx = -1 
        for col in columns:
            src = col['src']
            dst = col.get('dst', src)
            container, field = src.split('.', 1)

            if container == 'subject':
                container = 'session'
                field = src
            elif container not in COLUMN_CONTAINERS:
                raise InputValidationException('Unknown container for column: {}'.format(src))

            self.columns.append( (container, field, dst) )
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

    def get_all_columns(self):
        """Get all columns including auto generated id and label columns"""
        # Add default columns to the beginning
        columns = []

        include_ids = self.desc.get('includeIds', True)
        include_labels = self.desc.get('includeLabels', True)

        for cont in self.containers:
            if cont == 'session':
                # TODO: Remove once subjects are formalized
                if include_ids:
                    columns.append( ('session', 'subject._id', 'subject') )
                if include_labels:
                    columns.append( ('session', 'subject.code', 'subject_label') )

            if include_ids:
                columns.append(id_column(cont))
            if include_labels:
                columns.append(label_column(cont))

        return columns + self.columns

    def format_columns(self):
        """Format columns into a map of container -> columns, and include an index"""
        # Group columns by 
        columns = self.get_all_columns()

        for idx in range(len(columns)):
            container, src, dst = columns[idx]

            if container not in self.column_map:
                self.column_map[container] = []

            self.column_map[container].append((src, dst))
            self.flat_columns.append(dst)


