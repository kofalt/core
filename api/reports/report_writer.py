from .. import util
from ..data_views import formatters


class ReportWriter(object):
    """
    Class that permits writing a report in a variety of formats
    """

    def __init__(self, out_format, report):
        self._out_format = out_format
        self._formatter = formatters.get_formatter(out_format, self)
        self._write_fn = None
        self._report = report

    def execute(self, write_fn):
        """
        Execute a report, writing to the given write function
        """
        # Initialize write function
        self._write_fn = write_fn
        columns = self._report.columns

        for doc in self._report.build():
            # Flatten using dot notation
            row = util.mongo_dict(doc)

            # Perform any necessary type conversions
            self._report.format_row(row, self._out_format)

            # Write the row
            self._formatter.write_row(row, columns)

        self._formatter.finalize()

    def write(self, data):
        """
        Write-through to the underlying write function
        """
        return self._write_fn(data)

    def get_content_type(self):
        """
        Get the response Content-Type header value
        """
        return self._formatter.get_content_type()

    def get_filename(self):
        """
        Add the correct extension to report basename
        """
        ext = self._formatter.get_file_extension()
        return "{}{}".format(self._report.filename, ext)
