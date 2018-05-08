from .pipeline import PipelineStage, EndOfPayload

from ..readers import create_file_reader
from ..file_opener import FileOpener
from ..util import file_filter_to_regex

from ...config import log

class ReadFile(PipelineStage):
    def __init__(self, config):
        super(ReadFile, self).__init__()
        self.config = config
        self.error_rows = []
        self.file_columns_initialized = False

        zip_filter = self.config.file_spec.get('zipMember')
        if zip_filter:
            self.zip_filter = file_filter_to_regex(zip_filter)
        else:
            self.zip_filter = None

        self.file_format = self.config.file_spec.get('format')
        self.format_options = self.config.file_spec.get('formatOptions', {})

    def initialize_file_columns(self, reader):
        # file_data is a special column for file rows
        cols = self.config.file_spec.get('columns')
        if not cols:
            cols = [{'src': x} for x in reader.get_columns()]

        col_map = []
        for i in range(len(cols)):
            col = cols[i]

            src = col['src']
            dst = col.get('dst', src)

            col_map.append((src, dst))
            self.config.flat_columns.append(dst)

        # Add file_data column mappings
        self.config.column_map['file_data'] = col_map

    def process_file(self, context, file_entry):
        try:
            with FileOpener(file_entry, self.zip_filter) as opener:
                for filename, fd in opener.files():
                    self.process_file_data(context, filename, fd)
        except: # pylint: disable=bare-except
            log.exception('Could not open {}'.format(file_entry['name']))
            self.error_rows.append(context)

    def process_file_data(self, context, filename, fd):
        # Determine file columns if not specified
        reader = create_file_reader(fd, filename, self.file_format, self.format_options) 

        # On the first file, initialize the file columns
        if not self.file_columns_initialized:
            # Initialize file_columns
            self.initialize_file_columns(reader)

        for row in reader:
            new_row = context.copy()
            new_row['file_data'] = row
            self.emit(new_row)

    def process(self, payload):
        if payload == EndOfPayload:
            for row in self.error_rows:
                row['file_data'] = {}
                self.emit(row)

            self.emit(payload)
        else:
            file_entry = payload.get('file')
            if file_entry:
                self.process_file(payload, file_entry)
            else:
                self.error_rows.append(payload)

