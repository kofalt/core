import os
import csv

import json
import collections


def create_file_reader(fileobj, filename, file_format, options):
    """Create a filereader for the given file format (or autodetect type based on filename)
    
    Arguments:
        fileobj (file): The file object to read
        filename (str): The name of the file
        file_format (str): The optional file_format (or None or empty string to auto detect)
        options (dict): An optional set of options to pass into the file_formatter (e.g. csv options)

    Returns:
        object: The file reader object
    """
    # Determine file reader and options
    if not file_format:
        _, ext = os.path.splitext(filename)
        if ext == ".csv":
            file_format = "csv"
        elif ext == ".tsv":
            file_format = "tsv"
        elif ext == ".json":
            file_format = "json"
        else:
            raise RuntimeError("Could not auto-detect file type")

    if file_format == "csv" or file_format == "tsv":
        # Set default dialect for tsv files
        if "dialect" not in options and file_format == "tsv":
            options["dialect"] = "excel-tab"

        result = CsvFileReader()
        result.initialize(fileobj, options)
        return result

    if file_format == "json":
        result = JsonFileReader()
        result.initialize(fileobj, options)
        return result

    raise RuntimeError("Unsupported file format: {}".format(file_format))


class CsvFileReader(object):
    """File reader that can read comma or tab separated data files"""

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
    """File reader that can read JSON files (expects dictionary or list of dictionaries)"""

    # Arbitrary 10mb limit
    MAX_JSON_FILE_SIZE_BYTES = 10485760

    def __init__(self):
        self._json = None
        self._columns = []

    def initialize(self, fileobj, _options):
        max_size = JsonFileReader.MAX_JSON_FILE_SIZE_BYTES

        # Read up to max length bytes
        data = fileobj.read(max_size)
        if len(data) == max_size and fileobj.read(1):
            raise RuntimeError("File exceeds max length of {}".format(max_size))

        self._json = json.loads(data, object_pairs_hook=collections.OrderedDict)

        # Validate that we have a json list or object
        if not isinstance(self._json, (collections.Sequence, collections.Mapping)):
            raise RuntimeError("File does not contain a JSON list or object!")

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
