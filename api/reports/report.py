from abc import ABCMeta, abstractmethod

from .report_writer import ReportWriter
from .. import config
from ..auth import Privilege
from ..web.errors import APIReportException, APIReportParamsException

class Report(object):
    """Abstract class for building reports"""
    __metaclass__ = ABCMeta

    filename = 'report'
    columns = None
    required_role = Privilege.is_admin

    def __init__(self, params):
        """
        Initialize a Report
        """
        super(Report, self).__init__()
        self.params = params

    @abstractmethod
    def user_can_generate(self, uid, roles):
        """
        Check if user has required permissions to generate report
        """
        raise NotImplementedError()

    @abstractmethod
    def build(self):
        """
        Build and return a json report
        """
        raise NotImplementedError()

    def get_writer(self, out_format):
        """
        Get a writer for the given file format
        """
        if not self.columns:
            raise APIReportParamsException('This report does not support file export.')

        return ReportWriter(out_format, self)

    def format_row(self, row, out_format): # pylint: disable=unused-argument
        """
        Perform any necessary conversions to write the given flattened row.
        """
        pass

    @staticmethod
    def _get_result_list(cont_name, pipeline):
        """
        Helper function for extracting mongo aggregation results

        Runs a given mongo aggregation, throws APIReportException if
        there was a mongo error or if there are no results.
        """

        try:
            result = list(config.db[cont_name].aggregate(pipeline))
        except Exception as e:  # pylint: disable=broad-except
            raise APIReportException(str(e))

        if not result:
            raise APIReportException('no results')

        return result


    @staticmethod
    def _get_result(cont_name, pipeline):
        """
        Helper function for extracting a singular mongo aggregation result

        If more than one item is in the results array, throws APIReportException
        """

        results = Report._get_result_list(cont_name, pipeline)
        if len(results) == 1:
            return results[0]

        raise APIReportException
