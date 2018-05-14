from flywheel.models import (
    DataView,
    DataViewColumnSpec,
    DataViewFileSpec,
    DataViewAnalysisFilterSpec,
    DataViewNameFilterSpec
)

class DataViewBuilder(object):
    def __init__(self, label=None, public=False):
        self._label = label
        self._public = public
        self._columns = []
        self._file_columns = []
        self._file_container = None
        self._file_filter = None
        self._file_zip_filter = None
        self._file_format = None
        self._file_format_opts = {}
        self._file_match = None
        self._process_files = True
        self._analysis_filter = None
        self._include_labels = False
        self._include_ids = False
        self._missing_data_strategy = None

    def build(self):
        # Build the data view
        file_spec = None
        if self._file_container and self._file_filter:
            file_spec = DataViewFileSpec(
                container=self._file_container,
                analysis_filter=self._analysis_filter,
                filter=self._file_filter,
                zip_member=self._file_zip_filter,
                match=self._file_match,
                format=self._file_format,
                format_options=self._file_format_opts,
                process_files=self._process_files,
                columns=self._file_columns
            )
        elif (self._file_container or self._file_filter or
              self._file_columns or self._file_zip_filter or self._file_format or self._analysis_filter):
            raise ValueError('Both file_container and file_filter are required to process files!')

        return DataView(
            label=self._label,
            public=self._public,
            columns=self._columns,
            file_spec=file_spec,
            include_ids=self._include_ids,
            include_labels=self._include_labels,
            missing_data_strategy=self._missing_data_strategy
        )

    def label(self, label):
        self._label = label
        return self

    def public(self, value=True):
        self._public = value
        return self

    def column(self, src, dst=None, type=None):
        self._columns.append(DataViewColumnSpec(src=src, dst=dst, type=type))
        return self

    def file_column(self, src, dst=None, type=None):
        self._file_columns.append(DataViewColumnSpec(src=src, dst=dst, type=type))
        return self

    def file_container(self, container):
        self._file_container = container
        return self

    def file_match(self, match_value):
        self._file_match = match_value
        return self

    def analysis_filter(self, label=None, gear_name=None, regex=False):
        if (label is None and gear_name is None) or (label and gear_name):
            raise ValueError('Expected either label or gear_name')

        filter_spec = DataViewNameFilterSpec(value=(label or gear_name), regex=regex)

        if label:
            self._analysis_filter = DataViewAnalysisFilterSpec(label=filter_spec)
        else:
            self._analysis_filter = DataViewAnalysisFilterSpec(gear_name=filter_spec)
        return self

    def file_filter(self, value=None, regex=False):
        self._file_filter = DataViewNameFilterSpec(value=value, regex=regex)
        return self

    def zip_member_filter(self, value=None, regex=False):
        self._file_zip_filter = DataViewNameFilterSpec(value=value, regex=regex)
        return self

    def file_format(self, format_name):
        self._file_format = format_name
        return self

    def file_format_options(self, **kwargs):
        self._file_format_opts.update(kwargs)
        return self

    def process_files(self, value):
        self._process_files = value
        return self

    def include_labels(self, value=True):
        self._include_labels = value
        return self

    def include_ids(self, value=True):
        self._include_ids = value
        return self

    def missing_data_strategy(self, value):
        self._missing_data_strategy = value
        return self

