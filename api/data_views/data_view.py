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
import collections
import fnmatch
import re

from pprint import pprint

from .. import config, files
from ..auth import has_access
from ..dao import containerutil
from ..dao.basecontainerstorage import ContainerStorage, CHILD_MAP
from ..web.errors import APIPermissionException, APINotFoundException, InputValidationException

from .json_formatter import JsonFormatter
from .csv_reader import CsvFileReader
from .hierarchy_aggregator import HierarchyAggregator, AggregationStage

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

def is_phi_field(cont_type, src):
    next_part = src.split('.')[0]
    if cont_type == 'subject':
        if next_part not in ['_id', 'code']:
            return True
    elif next_part in ['subject', 'info']:
        return True

    return False

def extract_property(name, obj):
    path = name.split('.')
    for path_el in path:
        if isinstance(obj, collections.Sequence):
            try:
                obj = obj[int(path_el)]
            except IndexError:
                obj = None
            except ValueError:
                obj = None
        elif isinstance(obj, collections.Mapping):
            obj = obj.get(path_el, None)
        else:
            obj = getattr(obj, path_el, None)

        if obj is None:
            break

    return obj

def file_filter_to_regex(filter_spec):
    try:
        val = filter_spec['value']
        if not filter_spec.get('regex', False):
            val = fnmatch.translate(val)
        return re.compile(val, re.I)
    except re.error:
        raise InputValidationException('Invalid filter spec: {}'.format(filter_spec['value']))

class DataView(object):
    """Executes data view queries against the database."""
    def __init__(self, desc):
        # The original data view description
        self.desc = desc

        # Whether or not this query contains potential PHI
        self._phi_access = False

        # The set of accessed subjects
        self._accessed_subjects = set()

        # The original file spec, if there was one
        self._file_spec = desc.get('fileSpec', None)

        # The file container, or None
        self._file_container = None
        
        # The file filter, or None
        self._file_filter = None

        if self._file_spec:
            self._file_container = containerutil.singularize(self._file_spec['container'])
            self._file_filter = file_filter_to_regex(self._file_spec['filter'])
            self._phi_access = True # Any file access should be logged

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

        # The constructed aggregation pipeline
        self._aggregator = None

    def prepare(self, container_id, output_format, uid):
        """ Prepare the data view execution by looking up container_id and checking permissions.
        
        Args:
            container_id (str): The id of the container where view execution should start.
            output_format (str): The expected output format (e.g. json)
            uid (str): The user id to use when checking container permissions.        
        """
        if output_format == 'json':
            self._formatter = JsonFormatter()

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
        self._tree = [cont for cont in self._tree if cont['cont_type'] not in ['subjects', 'groups']]
        self._tree.reverse()

        # Check permissions
        for cont in self._tree:
            if not has_access(uid, cont, 'ro'):
                raise APIPermissionException('User {} does not have read access to {} {}'.format(uid, cont['cont_type'], cont['_id']))

            # Also build the context as we go
            cont_type = containerutil.singularize(cont['cont_type'])

            if cont_type == 'session':
                subject = cont.get('subject', {}).get('code')
                if subject:
                    self._accessed_subjects.add(subject)

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

            # Any subject fields (other than _id, or code) and any info fields are considered PHI
            if not self._phi_access and is_phi_field(container, src):
                self._phi_access = True

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

            self._column_map[container].append((src, dst, idx))

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
            for src, _dst, _idx in self._column_map.get(child_cont_type_singular, []):
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

            for src, dst, _idx in self._column_map[cont_type]:
                key = '{}.{}'.format(cont_type, src)
                context[dst] = extract_property(key, obj)

    def execute(self, write_fn):
        # Initialize the formatter
        self._formatter.initialize(write_fn, self._column_map)

        rows = self._aggregator.execute()
        # Access logging
        if self._phi_access:
            for row in rows:
                pprint(row)
                subject = row.pop(SUBJECT_CODE_KEY, None)
                if subject:
                    self._accessed_subjects.add(subject)

            print('TODO: Log PHI access for subjects {}'.format(', '.join(self._accessed_subjects)))

        # Extract as many values as possible into parent_context
        parent_context = {}
        self.extract_column_values(parent_context, self._context)

        for row in rows:
            cont_files = row.pop('files', None)

            # make a copy of context and update from row
            context = parent_context.copy()
            self.extract_column_values(context, row)

            # Find the first matching, non-deleted file
            if self._file_spec is not None:
                self.process_files(context, cont_files)
            else:
                self._formatter.write_row(context)

        self._formatter.finalize()

    def process_files(self, context, cont_files):
        matched_file = None

        # Find a matching, not-deleted file
        for f in cont_files:
            if 'deleted' in f:
                continue
            if self._file_filter.match(f['name']):
                matched_file = f
                break

        if matched_file:
            # Open file and pass to file reader
            reader = CsvFileReader()
            file_path, file_system = files.get_valid_file(matched_file)
            with file_system.open(file_path, 'r') as f:
                # Determine file columns
                reader.initialize(f, self._file_spec.get('formatOptions'))
                for row in reader:
                    row_context = context.copy()
                    row_context.update(row)

                    self._formatter.write_row(row_context)
        else:
            #TODO: Invoke missing data handler, possibly defer this row
            self._formatter.write_row(context)




