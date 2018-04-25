import csv

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
