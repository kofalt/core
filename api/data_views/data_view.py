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

from .. import config
from ..auth import has_access
from ..dao import containerutil
from ..dao.basecontainerstorage import ContainerStorage
from ..web.errors import APIPermissionException, APINotFoundException, InputValidationException

from .formatters import get_formatter
from .readers import create_file_reader
from .util import extract_json_property, file_filter_to_regex, nil_value
from .missing_data_strategies import get_missing_data_strategy
from .file_opener import FileOpener
from .config import DataViewConfig

from .pipeline.aggregate import Aggregate
from .pipeline.extract_columns import ExtractColumns
from .pipeline.log_access import LogAccess
from .pipeline.write import Write
from .pipeline.missing_data_strategies import get_missing_data_strategy

log = config.log

# TODO: subjects belong here once formalized
SEARCH_CONTAINERS = ['projects', 'sessions', 'acquisitions']

class DataView(object):
    """Executes data view queries against the database."""
    def __init__(self, desc):
        # The configuration object
        self.config = DataViewConfig(desc)

        # The content type
        self._content_type = None

        # The write function
        self._write_fn = None

        # The pipeline stage that logs access
        self._log_access_stage = LogAccess(self.config)

        # Contains the initial hierarchy tree for the target container
        self._tree = None

    def write(self, data):
        self._write_fn(data)

    def prepare(self, container_id, output_format, uid):
        """ Prepare the data view execution by looking up container_id and checking permissions.

        Then build the data pipeline.
        
        Args:
            container_id (str): The id of the container where view execution should start.
            output_format (str): The expected output format (e.g. json)
            uid (str): The user id to use when checking container permissions.        
        """
        # Initialize the column list
        self.config.initialize_columns()

        # Build the pipeline processor
        self.build_pipeline(output_format)

        # Search for starting container
        if bson.ObjectId.is_valid(container_id):
            container_id = bson.ObjectId(container_id)

        result = containerutil.container_search({'_id': container_id}, collections=SEARCH_CONTAINERS)
        if not result:
            raise APINotFoundException('Could not resolve container: {}'.format(container_id))
        cont_type, search_results = result[0] # First returned collection

        # Get the container tree (minus group, and subjec)
        # TODO: Allow subjects once formalized
        storage = ContainerStorage.factory(cont_type)
        self._tree = storage.get_parent_tree(container_id, cont=search_results[0], add_self=True)

        # Set access log initial context (including group)
        self._log_access_stage.initialize(self._tree)
        
        self._tree = [cont for cont in self._tree if cont['cont_type'] not in ['subjects', 'groups']]
        self._tree.reverse()

        # Check permissions
        for cont in self._tree:
            if not has_access(uid, cont, 'ro'):
                raise APIPermissionException('User {} does not have read access to {} {}'.format(uid, cont['cont_type'], cont['_id']))

    def build_pipeline(self, output_format):
        config = self.config

        # First stage is aggregation
        self.pipeline = Aggregate(config)

        # If there is an analysis filter, then we have an extract analyses phase

        # Add access log stage
        self.pipeline.pipe(self._log_access_stage)

        # Add extraction stage
        self.pipeline.pipe(ExtractColumns(config))

        # Add missing data stage
        missing_data_strategy = config.desc.get('missingDataStrategy')
        missing_data_stage = get_missing_data_strategy(missing_data_strategy)
        self.pipeline.pipe(missing_data_stage)

        # Add the output stage
        formatter = get_formatter(output_format, self)
        self._content_type = formatter.get_content_type()
        self.pipeline.pipe(Write(config, formatter))

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
        return self._content_type

    def execute(self, request, origin, write_fn):
        # Store the write_fn so write() calls succeed
        self._write_fn = write_fn

        # Set the request/origin on access log
        self._log_access_stage.set_request_origin(request, origin)

        self.pipeline.process(self._tree)
        return ''

        """
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

            rows.append( (context, file_entry) )

        # Initialize the formatter
        self._formatter.initialize(write_fn)

        # Extract as many values as possible into parent_context
        rows_missing_files = []
        for context, file_entry in rows:
            if self._file_spec:
                if file_entry:
                    if not self.process_file(context, file_entry):
                        rows_missing_files.append(context)
                else:
                    rows_missing_files.append(context)
            else:
                self._writer.write_row(context, self._flat_columns)

        if rows_missing_files:
            for row in rows_missing_files:
                # Handle missing file data by replacing values with nil
                for _, dst in self._file_columns:
                    row[dst] = nil_value

                self._writer.write_row(row, self._flat_columns, nil_hint=True)
            
        self._formatter.finalize()
        """
    
    def match_file(self, files):
        # Find a matching, not-deleted file
        if files is not None:
            for f in files:
                if 'deleted' in f:
                    continue
                if self._file_filter.match(f['name']):
                    return f

        return None

    def process_file(self, context, file_entry):
        try:
            with FileOpener(file_entry, self._zip_file_filter) as opened_file:
                self.process_file_data(context, opened_file.name, opened_file.fd)
            return True
        except: # pylint: disable=bare-except
            log.exception('Could not open {}'.format(file_entry['name']))
            return False

    def process_file_data(self, context, filename, fd):
        # Determine file columns if not specified
        reader = create_file_reader(fd, filename, 
            self._file_spec.get('format'), self._file_spec.get('formatOptions', {}))

        # On the first file, initialize the file columns
        if not self._file_columns:
            # Initialize file_columns
            self.initialize_file_columns(reader)

        for row in reader:
            row_context = context.copy()

            for src, dst in self._file_columns:
                row_context[dst] = row.get(src, nil_value)

            self._writer.write_row(row_context, self._flat_columns)



