import csv
import json
from ..web.encoder import custom_json_serializer

def get_formatter(strategy, fileobj):
    """Get a row formatter strategy based on name
    
    Arguments:
        strategy (str): The output strategy (one of: json, json-row-column, csv, tsv)

    Returns:
        object: The formatting strategy
    """
    if not strategy or strategy == 'json':
        return JsonObjectFormatter(fileobj)
    if strategy == 'json-row-column':
        return JsonRowColumnFormatter(fileobj)
    if strategy == 'csv':
        return CsvFormatter(fileobj)
    if strategy == 'tsv':
        return CsvFormatter(fileobj, dialect='excel-tab')
    raise ValueError('Unknown formatter type: {}'.format(strategy))

class JsonObjectFormatter(object):
    """A formatting strategy that will write a JSON list of objects"""
    def __init__(self, fileobj):
        self._file = fileobj 
        self._first_row = True

    def get_content_type(self):
        return 'application/json; charset=utf-8'

    def write_row(self, context, dummy_columns):
        if self._first_row:
            self._file.write('{"data":[')
        else:
            self._file.write(',')

        json.dump(context, self._file, default=custom_json_serializer)
        self._first_row = False

    def finalize(self):
        # If we wrote no rows, write an empty array
        if self._first_row:
            self._file.write('{"data":[]}')
        else:
            self._file.write(']}')

class JsonRowColumnFormatter(object):
    """A formatting strategy that will write a JSON list of columns, then a list of lists of values (rows)"""
    def __init__(self, fileobj):
        self._file = fileobj 
        self._first_row = True

    def get_content_type(self):
        return 'application/json; charset=utf-8'

    def write_row(self, context, columns):
        if self._first_row:
            columns_json = json.dumps(columns)
            self._file.write('{{"data":{{"columns":{},"rows":['.format(columns_json))
        else:
            self._file.write(',')

        row = []
        for col in columns:
            row.append(context[col])

        row = json.dumps(row, default=custom_json_serializer)
        self._file.write(row)

        self._first_row = False

    def finalize(self):
        # If we wrote no rows, write an empty array
        if self._first_row:
            self._file.write('{"data":{"columns":[],"rows":[]}}')
        else:
            self._file.write(']}}')

class CsvFormatter(object):
    """A formatting strategy that will write a comma or tab separated value file"""
    def __init__(self, fileobj, dialect='excel'):
        self.dialect = dialect
        self._file = fileobj 
        self._writer = None

    def get_content_type(self):
        if self.dialect == 'excel-tab':
            return 'text/tab-separated-values; charset=utf-8'
        return 'text/csv; charset=utf-8'

    def write_row(self, context, columns):
        if not self._writer:
            # NOTE: csv writer can take any object with a `write` function, in this case that's us
            # See: https://docs.python.org/2/library/csv.html#csv.writer
            self._writer = csv.DictWriter(self._file, fieldnames=columns, dialect=self.dialect, extrasaction='ignore')
            self._writer.writeheader()

        self._writer.writerow(context)

    def finalize(self):
        pass

