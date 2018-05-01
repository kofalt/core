
import json
from ..web.encoder import custom_json_serializer

def get_formatter(strategy):
    if not strategy or strategy == 'json':
        return JsonObjectFormatter()
    raise ValueError('Unknown formatter type: {}'.format(strategy))

class JsonObjectFormatter(object):
    def __init__(self):
        self._write = None
        self._first_row = True

    def get_content_type(self):
        return 'application/json; charset=utf-8'

    def initialize(self, write_fn, columns):
        self._write = write_fn
        self._columns = columns

    def write_row(self, context):
        if self._first_row:
            self._write('[')
        else:
            self._write(',')

        row = json.dumps(context, default=custom_json_serializer)
        self._write(row)

        self._first_row = False

    def finalize(self):
        self._write(']')
