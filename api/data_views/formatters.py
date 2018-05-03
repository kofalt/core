import csv
import json
from ..web.encoder import custom_json_serializer

def get_formatter(strategy):
    if not strategy or strategy == 'json':
        return JsonObjectFormatter()
    if strategy == 'json-row-column':
        return JsonRowColumnFormatter()
    if strategy == 'csv':
        return CsvFormatter()
    if strategy == 'tsv':
        return CsvFormatter(dialect='excel-tab')
    raise ValueError('Unknown formatter type: {}'.format(strategy))

class JsonObjectFormatter(object):
    def __init__(self):
        self._write = None
        self._first_row = True

    def get_content_type(self):
        return 'application/json; charset=utf-8'

    def initialize(self, write_fn):
        self._write = write_fn

    def write_row(self, context, columns):
        if self._first_row:
            self._write('{"data":[')
        else:
            self._write(',')

        row = json.dumps(context, default=custom_json_serializer)
        self._write(row)

        self._first_row = False

    def finalize(self):
        # If we wrote no rows, write an empty array
        if self._first_row:
            self._write('{"data":[]}')
        else:
            self._write(']}')

class JsonRowColumnFormatter(object):
    def __init__(self):
        self._write = None
        self._first_row = True

    def get_content_type(self):
        return 'application/json; charset=utf-8'

    def initialize(self, write_fn):
        self._write = write_fn

    def write_row(self, context, columns):
        if self._first_row:
            columns_json = json.dumps(columns)
            self._write('{{"data":{{"columns":{},"rows":['.format(columns_json))
        else:
            self._write(',')

        row = []
        for col in columns:
            row.append(context[col])

        row = json.dumps(row, default=custom_json_serializer)
        self._write(row)

        self._first_row = False

    def finalize(self):
        # If we wrote no rows, write an empty array
        if self._first_row:
            self._write('{"data":{"columns":[],"rows":[]}}')
        else:
            self._write(']}}')

class CsvFormatter(object):
    def __init__(self, dialect='excel'):
        self.dialect = dialect
        self._write = None
        self._writer = None

    def get_content_type(self):
        if self.dialect == 'excel-tab':
            return 'text/tab-separated-values; charset=utf-8'
        return 'text/csv; charset=utf-8'

    def initialize(self, write_fn):
        self._write = write_fn

    def write(self, data):
        self._write(data)

    def write_row(self, context, columns):
        if not self._writer:
            # NOTE: csv writer can take any object with a `write` function, in this case that's us
            # See: https://docs.python.org/2/library/csv.html#csv.writer
            self._writer = csv.DictWriter(self, fieldnames=columns, dialect=self.dialect, extrasaction='ignore')
            self._writer.writeheader()

        self._writer.writerow(context)

    def finalize(self):
        pass

