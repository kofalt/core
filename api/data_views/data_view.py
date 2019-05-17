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

from ..auth import has_access
from ..dao import containerutil
from ..dao.basecontainerstorage import ContainerStorage
from ..web.errors import InputValidationException, APINotFoundException, APIPermissionException, APIValidationException

from .formatters import get_formatter
from .config import DataViewConfig

from .pipeline.aggregate import Aggregate
from .pipeline.discover_columns import DiscoverColumns
from .pipeline.extract_columns import ExtractColumns
from .pipeline.log_access import LogAccess
from .pipeline.match_containers import MatchContainers
from .pipeline.write import Write
from .pipeline.read_file import ReadFile
from .pipeline.missing_data_strategies import get_missing_data_strategy
from .pipeline.filter import Filter
from .pipeline.skip_limit import SkipAndLimit
from .pipeline.report_progress import ReportProgress

SEARCH_CONTAINERS = ["projects", "subjects", "sessions", "acquisitions"]

ANALYSIS_FILTER_COLUMNS = [("label", "label"), ("gear.name", "gear_info.name"), ("gear.version", "gear_info.version")]


class DataView(object):
    """Executes data view queries against the database."""

    def __init__(self, desc):
        # The configuration object
        self.config = DataViewConfig(desc)

        # The processing pipeline
        self.pipeline = None

        # The content type for the response
        self._content_type = None

        # The file extension for the response
        self._file_extension = ".bin"

        # The write function
        self._write_fn = None

        # The write progress function
        self._write_progress_fn = None

        # The pipeline stage that logs access
        self._log_access_stage = LogAccess(self.config)

        # Contains the initial hierarchy tree for the target container
        self._tree = None

    def validate_config(self):
        """Validate the data view configuration"""
        self.config.validate()

    def write(self, data):
        """Write data to the response"""
        self._write_fn(data)

    def write_progress(self, data):
        """Write progress data to the response"""
        if self._write_progress_fn:
            self._write_progress_fn(data)

    def prepare(self, container_id, output_format, uid, pagination=None, report_progress=False):
        """Prepare the data view execution by looking up container_id and checking permissions.

        Then build the data pipeline.
        
        Args:
            container_id (str): The id of the container where view execution should start.
            output_format (str): The expected output format (e.g. json)
            uid (str): The user id to use when checking container permissions.        
            pagination (dict): The optional pagination options (including filtering)
        """
        # Don't support sorting in pagination
        if pagination and "sort" in pagination:
            raise APIValidationException("Sorting is not supported for data views")

        # Initialize the column list
        self.config.initialize_columns()

        # Build the pipeline processor
        self.build_pipeline(output_format, pagination, report_progress)

        # Search for starting container
        if bson.ObjectId.is_valid(container_id):
            container_id = bson.ObjectId(container_id)

        result = containerutil.container_search({"_id": container_id}, collections=SEARCH_CONTAINERS)
        if not result:
            raise APINotFoundException("Could not resolve container: {}".format(container_id))
        cont_type, search_results = result[0]  # First returned collection

        # Get the container tree (minus group)
        storage = ContainerStorage.factory(cont_type)
        self._tree = storage.get_parent_tree(container_id, cont=search_results[0], add_self=True)

        # Set access log initial context (including group)
        self._log_access_stage.initialize(self._tree)

        self._tree = [cont for cont in self._tree if cont["cont_type"] != "groups"]
        self._tree.reverse()

        # Check permissions
        for cont in self._tree:
            if not has_access(uid, cont, "ro"):
                raise APIPermissionException("User {} does not have read access to {} {}".format(uid, cont["cont_type"], cont["_id"]))

    def build_pipeline(self, output_format, pagination, report_progress):
        config = self.config
        formatter = get_formatter(output_format, self)

        # Add filtered columns to the spec
        filter_spec = None
        if pagination and "filter" in pagination:
            filter_spec = pagination["filter"]
            for key in filter_spec.keys():
                dst = "_filter.{}".format(key)
                container = config.resolve_and_add_column(key, dst)
                if container not in config.containers:
                    raise InputValidationException("Cannot filter on key: {}, container {} is not part of the retrieval".format(key, container))

        # First stage is aggregation
        self.pipeline = Aggregate(config)

        # Add match files stage
        if config.file_spec:
            files_key = "files"

            match_type = config.get_file_match_type()

            # Optionally add analysis filter
            if config.analysis_filter:
                analysis_filters = []

                for name, key in ANALYSIS_FILTER_COLUMNS:
                    if name in config.analysis_filter:
                        analysis_filters.append((key, config.analysis_filter[name]))

                match_analyses = MatchContainers("analysis", "analysis", analysis_filters, match_type)
                self.pipeline.pipe(match_analyses)
                files_key = "analysis.files"

            match_files = MatchContainers(files_key, "file", [("name", config.file_spec["filter"])], match_type)
            self.pipeline.pipe(match_files)

        # Add access log stage
        self.pipeline.pipe(self._log_access_stage)

        # Add process files stage
        if config.file_spec and config.file_spec.get("processFiles") != False:
            self.pipeline.pipe(ReadFile(config))

        # Add the column flattening stage
        if formatter.is_flat_output():
            self.pipeline.pipe(DiscoverColumns(config))

        # Add extraction stage
        self.pipeline.pipe(ExtractColumns(config))

        # Add optional filter stage
        if filter_spec:
            self.pipeline.pipe(Filter(filter_spec))

        # Add missing data stage
        missing_data_strategy = config.desc.get("missingDataStrategy")
        missing_data_stage = get_missing_data_strategy(missing_data_strategy)
        self.pipeline.pipe(missing_data_stage)

        # Add the optional limit stage
        if pagination and ("limit" in pagination or "skip" in pagination):
            self.pipeline.pipe(SkipAndLimit(pagination))

        # Add the optional progress report stage
        if report_progress:
            self.pipeline.pipe(ReportProgress(self))

        # Add the output stage
        self._content_type = formatter.get_content_type()
        self._file_extension = formatter.get_file_extension()
        self.pipeline.pipe(Write(config, formatter))

    def get_content_type(self):
        """Get the response Content-Type header value"""
        return self._content_type

    def get_filename(self, basename):
        """Add the correct extension to basename"""
        return "{}{}".format(basename, self._file_extension)

    def execute(self, request, origin, write_fn, write_progress_fn=None):
        # Store the write_fn so write() calls succeed
        self._write_fn = write_fn
        self._write_progress_fn = write_progress_fn

        # Set the request/origin on access log
        self._log_access_stage.set_request_origin(request, origin)

        self.pipeline.process(self._tree)
        return ""
