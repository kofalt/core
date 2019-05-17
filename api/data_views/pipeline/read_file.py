from .pipeline import PipelineStage, EndOfPayload

from ..readers import create_file_reader
from ..file_opener import FileOpener
from ..util import file_filter_to_regex, is_nil, nil_value

from ...config import log


class ReadFile(PipelineStage):
    """Pipeline stage that will read the file entry, possibly extracting a zip member.

    Expects a single row (or EndOfPayload) that has a 'file' member of the file to open.
    Emits a row for each row found in the file (or files if multiple zip members)
    """

    def __init__(self, config):
        """Initialize the pipeline stage.

        Arguments:
            config (DataViewConfig): The data view configuration
        """
        super(ReadFile, self).__init__()
        self.config = config
        self.error_rows = []
        self.file_columns_initialized = False

        zip_filter = self.config.file_spec.get("zipMember")
        if zip_filter:
            self.zip_filter = file_filter_to_regex(zip_filter)
        else:
            self.zip_filter = None

        self.file_format = self.config.file_spec.get("format")
        self.format_options = self.config.file_spec.get("formatOptions", {})

    def initialize_file_columns(self, reader):
        """Initialize the file columns based on the config, or set of columns discovered by the file reader"""
        # file_data is a special column for file rows
        cols = self.config.file_spec.get("columns")
        if not cols:
            cols = [{"src": x} for x in reader.get_columns()]

        for i in range(len(cols)):
            col = cols[i]

            src = col["src"]
            dst = col.get("dst", src)
            datatype = col.get("type")

            self.config.add_column("file_data", src, dst, datatype)

        self.file_columns_initialized = True

    def process_file(self, context, file_entry):
        """Process the given file entry

        Arguments:
            context (dict): The current context
            file_entry (dict): The file entry to process
        """
        try:
            with FileOpener(file_entry, self.zip_filter) as opener:
                for filename, fd in opener.files():
                    self.process_file_data(context, filename, fd)
        except:  # pylint: disable=bare-except
            log.exception("Could not open {}".format(file_entry["name"]))
            self.error_rows.append(context)

    def process_file_data(self, context, filename, fd):
        """Process the data in the given file.

        Arguments:
            context (dict): The current context
            filename (str): The name of the opened file (e.g. the zip file name, or file_entry['name'])
            fd (file): The file object
        """
        # Determine file columns if not specified
        reader = create_file_reader(fd, filename, self.file_format, self.format_options)

        # On the first file, initialize the file columns
        if not self.file_columns_initialized:
            # Initialize file_columns
            self.initialize_file_columns(reader)

        for row_number, row in enumerate(reader):
            row["_index"] = row_number
            new_row = context.copy()
            new_row["file_data"] = row
            self.emit(new_row)

    def process(self, payload):
        if payload == EndOfPayload:
            for row in self.error_rows:
                row["file_data"] = {}
                self.emit(row)

            self.emit(payload)
        else:
            file_entry = payload.get("file", nil_value)
            if not is_nil(file_entry):
                self.process_file(payload, file_entry)
            else:
                self.error_rows.append(payload)
