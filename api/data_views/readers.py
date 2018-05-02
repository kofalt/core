import os
import csv

def create_file_reader(fileobj, filename, format, options):
    # Determine file reader and options
    print('create file reader for file: {}, format: {}'.format(filename, format))
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
        print('Autodetected format: {}'.format(format))

    if format == 'csv' or format == 'tsv':
        # Set default dialect for tsv files
        if 'dialect' not in options and format == 'tsv':
            options['dialect'] = 'excel-tab'

        result = CsvFileReader()
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

