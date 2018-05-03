import os
import csv

import json
import collections

def create_file_reader(fileobj, filename, format, options):
    # Determine file reader and options
    if not format:
        root, ext = os.path.splitext(filename)
        if ext == '.csv':
            format = 'csv'
        elif ext == '.tsv':
            format = 'tsv'
        elif ext == '.json':
            format = 'json'
        else:
            raise RuntimeError('Could not auto-detect file type')

    if format == 'csv' or format == 'tsv':
        # Set default dialect for tsv files
        if 'dialect' not in options and format == 'tsv':
            options['dialect'] = 'excel-tab'

        result = CsvFileReader()
        result.initialize(fileobj, options)
        return result

    if format == 'json':
        result = JsonFileReader()
        result.initialize(fileobj, options)
        return result
    
    raise RuntimeError('Unsupporetd file format: {}'.format(format))

class CsvFileReader(object):
    def __init__(self):
        self._reader = None
        self._columns = None

    def initialize(self, fileobj, options):
        if options is None:
            options = {}

        self._reader = csv.DictReader(fileobj, **options)

    def __iter__(self):
        return self._reader

    def get_columns(self):
        return self._reader.fieldnames

class JsonFileReader(object):
    # Arbitrary 10mb limit
    MAX_JSON_FILE_SIZE_BYTES = 10485760

    def __init__(self):
        self._json = None
        self._columns = []

    def initialize(self, fileobj, options):
        max_size = JsonFileReader.MAX_JSON_FILE_SIZE_BYTES

        # Read up to max length bytes
        data = fileobj.read(max_size)
        if len(data) == max_size and fileobj.read(1):
            raise RuntimeError('File exceeds max length of {}'.format(max_size))

        self._json = json.loads(data, object_pairs_hook=collections.OrderedDict)

        # Validate that we have a json list or object
        if not isinstance(self._json, (collections.Sequence, collections.Mapping)):
            raise RuntimeError('File does not contain a JSON list or object!')

        # Wrap in a list
        if isinstance(self._json, collections.Mapping):
            self._json = [self._json]
        
        # Extract columns
        self._init_columns()

    def _init_columns(self):
        if self._json:
            first_row = self._json[0]
            if isinstance(first_row, collections.Mapping):
                self._columns = first_row.keys()

    def __iter__(self):
        return iter(self._json)

    def get_columns(self):
        return self._columns

