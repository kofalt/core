"""
    Stages of processing:
        1. Find the source container by id
        2. Build the parent tree so that we have project nodes on down
        3. Initialize an output collector/streamer
        4. Given the initial tree, build the pipeline to match record values and files.
            a. Also determine if PHI is accessed (yes if any info.* or file)
        5. Perform initial query to get initial set of matched rows.
        6. If there are files, retrieve all files and process according to algorithm.
            7. Process files, producing output. 
            
"""
import bson
import re

from pprint import pprint

from .. import config, files
from ..auth import has_access
from ..dao import containerutil
from ..dao.basecontainerstorage import ContainerStorage, CHILD_MAP
from ..web.errors import APIPermissionException, APINotFoundException, InputValidationException

from .access_logger import create_access_logger
from .formatters import get_formatter
from .csv_reader import CsvFileReader
from .hierarchy_aggregator import HierarchyAggregator, AggregationStage
from .util import extract_json_property, file_filter_to_regex, nil_value
from .missing_data_strategies import get_missing_data_strategy
from .file_opener import FileOpener

log = config.log

# TODO: subjects belong here once formalized
VIEW_CONTAINERS = [ 'project', 'session', 'acquisition' ]
SEARCH_CONTAINERS = ['projects', 'sessions', 'acquisitions']

# Key in the pipeline that is always populated with the subject code
SUBJECT_CODE_KEY = '_subject_code'

def normalize_id(val):
    if re.match('^[a-f\d]{24}$', val):
        return bson.ObjectId(val)
    return val

def id_column(cont_type):
    return ( cont_type, '_id', cont_type )

def label_column(cont_type):
    return ( cont_type, 'label', '{}_label'.format(cont_type) )

def get_child_cont_type(cont_type):
    # TODO: Replace with ContainerStorage.child_cont_name
    return CHILD_MAP.get(containerutil.pluralize(cont_type))

class DataView(object):
    """Executes data view queries against the database."""
    def __init__(self, desc):
        # The original data view description
        self.desc = desc

        # The access logger
        self._access_log = create_access_logger()

        # The original file spec, if there was one
        self._file_spec = desc.get('fileSpec', None)

        # The file container, or None
        self._file_container = None
        
        # The file filter, or None
        self._file_filter = None

        # The file columns
        self._file_columns = []

        # The zip file filter or None
        self._zip_file_filter = None

        if self._file_spec:
            self._file_container = containerutil.singularize(self._file_spec['container'])
            self._file_filter = file_filter_to_regex(self._file_spec['filter'])
            self._access_log.set_file_container(self._file_container)

            zip_filter = self._file_spec.get('zipMember')
            if zip_filter:
                self._zip_file_filter = file_filter_to_regex(zip_filter)

        # Contains the initial hierarchy tree for the target container
        self._tree = None

        # The initial context, built from the hierarchy tree
        self._context = {}

        # Output formatter instance
        self._formatter = None

        # The list of containers that will be queried as part of the pipeline
        self._containers = []

        # The user-defined set of columns, as tuples of (container, src, dst)
        self._columns = []

        # A map of container to columns for that container that includes column indexes
        self._column_map = {}

        # The ordered set of columns
        self._flat_columns = []

        # The constructed aggregation pipeline
        self._aggregator = None

        # The row writer
        self._writer = None

    def prepare(self, container_id, output_format, uid):
        """ Prepare the data view execution by looking up container_id and checking permissions.
        
        Args:
            container_id (str): The id of the container where view execution should start.
            output_format (str): The expected output format (e.g. json)
            uid (str): The user id to use when checking container permissions.        
        """
        self._formatter = get_formatter(output_format)

        missing_data_strategy = self.desc.get('missingDataStrategy')
        self._writer = get_missing_data_strategy(missing_data_strategy, self._formatter)

        container_id = normalize_id(container_id)

        # Check file container
        if self._file_container and self._file_container not in VIEW_CONTAINERS:
            raise InputValidationException('Unexpected file container: {}'.format(self._file_spec['container']))

        # Search for starting container
        result = containerutil.container_search({'_id': container_id}, collections=SEARCH_CONTAINERS)
        if not result:
            raise APINotFoundException('Could not resolve container: {}'.format(container_id))
        cont_type, search_results = result[0] # First returned collection

        # Get the container tree (minus group, and subjec)
        # TODO: Allow subjects once formalized
        storage = ContainerStorage.factory(cont_type)
        self._tree = storage.get_parent_tree(container_id, cont=search_results[0], add_self=True)

        # Set access log initial context (including group)
        self._access_log.create_context(self._tree)
        
        self._tree = [cont for cont in self._tree if cont['cont_type'] not in ['subjects', 'groups']]
        self._tree.reverse()

        # Check permissions
        for cont in self._tree:
            if not has_access(uid, cont, 'ro'):
                raise APIPermissionException('User {} does not have read access to {} {}'.format(uid, cont['cont_type'], cont['_id']))

            # Also build the context as we go
            cont_type = containerutil.singularize(cont['cont_type'])

            self._context[cont_type] = cont

        # Build the pipeline query
        self.determine_fetch_containers()
        self.format_columns()
        self.build_pipeline()

    def determine_fetch_containers(self):
        """Determine how deep we need to fetch based on columns and file specs"""
        max_idx = -1 
        for col in self.desc['columns']:
            src = col['src']
            dst = col.get('dst', src)
            container, field = src.split('.', 1)

            # Any subject fields and any info fields are considered PHI
            if self._access_log.is_phi_field(container, field):
                self._access_log.add_container(container)

            if container == 'subject':
                container = 'session'
                field = src
            elif container not in  VIEW_CONTAINERS:
                raise InputValidationException('Unknown container for column: {}'.format(src))

            self._columns.append( (container, field, dst) )
            max_idx = max(max_idx, VIEW_CONTAINERS.index(container))

        # Check file spec container as well
        if self._file_container:
            file_idx = VIEW_CONTAINERS.index(self._file_container)
            # If there are columns specified below the file_container, that's an error
            if file_idx < max_idx:
                raise InputValidationException('File match must be the lowest container on the hierarchy')
            max_idx = max(max_idx, file_idx)

        assert max_idx > -1
        self._containers = VIEW_CONTAINERS[:max_idx+1]

    def get_all_columns(self):
        """Get all columns including auto generated id and label columns"""
        # Add default columns to the beginning
        columns = []

        include_ids = self.desc.get('includeIds', True)
        include_labels = self.desc.get('includeLabels', True)

        for cont in self._containers:
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

        return columns + self._columns

    def format_columns(self):
        """Format columns into a map of container -> columns, and include an index"""
        # Group columns by 
        columns = self.get_all_columns()

        for idx in range(len(columns)):
            container, src, dst = columns[idx]

            if container not in self._column_map:
                self._column_map[container] = []

            self._column_map[container].append((src, dst))
            self._flat_columns.append(dst)

    def initialize_file_columns(self, reader):
        # file_data is a special column for file rows
        cols = self._file_spec.get('columns')
        if not cols:
            cols = [{'src': x} for x in reader.get_columns()]

        for i in range(len(cols)):
            col = cols[i]

            src = col['src']
            dst = col.get('dst', src)

            self._file_columns.append((src, dst))
            self._flat_columns.append(dst)

    def get_content_type(self):
        return self._formatter.get_content_type()

    def build_pipeline(self):
        cont_type = self._tree[-1]['cont_type']
        cont_id = self._tree[-1]['_id']

        # Determine the total depth
        aggregator = HierarchyAggregator()
        for idx in range(len(self._tree), len(self._containers)):
            child_cont_type = get_child_cont_type(cont_type)
            child_cont_type_singular = containerutil.singularize(child_cont_type)

            if not aggregator.stages:
                # Setup initial filtering
                key_name = containerutil.singularize(cont_type)
                aggregator.filter_spec = { key_name: cont_id }

            stage = AggregationStage(child_cont_type)
            for src, _dst in self._column_map.get(child_cont_type_singular, []):
                stage.fields.append(src)

            # TODO: Should become if 'subject' then '$code' 
            if child_cont_type == 'sessions':
                stage.fields.append( (SUBJECT_CODE_KEY, 'subject.code') )

            if child_cont_type_singular == self._file_container:
                stage.fields.append( ('files', 'files') )

            aggregator.stages.append(stage) 

            # Advance cont_type
            cont_type = child_cont_type

        self._aggregator = aggregator

    def extract_column_values(self, context, obj):
        for cont_type, cont in obj.items():
            if cont_type not in self._column_map:
                continue

            for src, dst in self._column_map[cont_type]:
                key = '{}.{}'.format(cont_type, src)
                context[dst] = extract_json_property(key, obj, default=nil_value)

    def execute(self, request, origin, write_fn):
        # Execute the aggregation query
        cursor = self._aggregator.execute()

        parent_context = {}
        self.extract_column_values(parent_context, self._context)

        # Build context values
        rows = []
        for row in cursor:
            # Build context, match file, and perform access log
            cont_files = row.pop('files', None)

            # Log context
            meta = row.pop('_meta', None)

            # make a copy of context and update from row
            context = parent_context.copy()
            self.extract_column_values(context, row)

            # Find the first matching, non-deleted file
            if self._file_spec is not None:
                file_entry = self.match_file(cont_files)
                if file_entry:
                    filename = file_entry['name']
                else:
                    filename = None
            else:
                file_entry = None
                filename = None

            # Add access log entries for this context/file
            self._access_log.add_entries(meta, filename)

            rows.append( (context, file_entry) )

        # Write all of the access logs. If this fails, abort the request (allow exception to pass through)
        self._access_log.write_logs(request, origin)

        # Initialize the formatter
        self._formatter.initialize(write_fn)

        # Extract as many values as possible into parent_context
        rows_missing_files = []
        for context, file_entry in rows:
            if self._file_spec:
                if file_entry:
                    if not self.process_file(context, file_entry, write_fn):
                        rows_missing_files.append(context)
                else:
                    rows_missing_files.append(context)
            else:
                self._writer.write_row(context, self._flat_columns)

        if rows_missing_files:
            for row in rows_missing_files:
                # Handle missing file data by replacing values with nil
                for _src, dst in self._file_columns:
                    row[dst] = nil_value

                self._writer.write_row(row, self._flat_columns, nil_hint=True)
            
        self._formatter.finalize()
    
    def match_file(self, files):
        # Find a matching, not-deleted file
        if files is not None:
            for f in files:
                if 'deleted' in f:
                    continue
                if self._file_filter.match(f['name']):
                    return f

        return None

    def process_file(self, context, file_entry, write_fn):
        try:
            with FileOpener(file_entry, self._zip_file_filter) as opened_file:
                self.process_file_data(context, opened_file.fd, write_fn)
            return True
        except Exception:
            log.exception('Could not open {}'.format(file_entry['name']))
            return False

    def process_file_data(self, context, fd, write_fn):
        # Determine file columns if not specified
        reader = CsvFileReader()
        reader.initialize(fd, self._file_spec.get('formatOptions'))

        # On the first file, initialize the file columns
        if not self._file_columns:
            # Initialize file_columns
            self.initialize_file_columns(reader)

        for row in reader:
            row_context = context.copy()

            for src, dst in self._file_columns:
                row_context[dst] = row.get(src, nil_value)

            self._writer.write_row(row_context, self._flat_columns)



