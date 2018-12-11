import datetime

from .. import config

from ..metrics import values
from ..reports import ReportTypes
from ..web import base, encoder
from ..web.request import AccessTypeList
from ..web.errors import APIPermissionException

log = config.log

class ReportHandler(base.RequestHandler):
    """Handles report requests

    To add a new report, declare a subclass of Report,
    and add it to the ReportTypes map in __init__.py
    """
    def get_types(self):
        return AccessTypeList

    def get(self, report_type):
        report = self._get_report(report_type)

        if self.is_true('csv'):
            download_format = 'csv'
        else:
            download_format = self.get_param('download')

        if download_format:
            # Stream the response
            def response_handler(environ, start_response): # pylint: disable=unused-argument
                report_writer = report.get_writer(download_format)

                write = start_response('200 OK', [
                    ('Content-Type', report_writer.get_content_type()),
                    ('Content-Disposition', 'attachment; filename="{}"'.format(report_writer.get_filename())),
                    ('Connection', 'keep-alive')
                ])

                report_writer.execute(write)
                return ''

            return response_handler
        else:
            return report.build()

    def collect(self, report_type):
        report = self._get_report(report_type)
        if not report.can_collect:
            raise NotImplementedError('Report type {} does not support collection'.format(report_type))

        # Invoke input validation for report collection
        report.before_collect()

        def sse_handler(environ, start_response): # pylint: disable=unused-argument
            write = start_response('200 OK', [
                ('Content-Type', 'text/event-stream; charset=utf-8'),
                ('Connection', 'keep-alive')
            ])

            # Instead of handing the iterator off to response.app_iter, send it ourselves.
            # This prevents disconnections from leaving the API in a partially-complete state.
            #
            # Timing out between events or throwing an exception will result in undefinied behaviour.
            # Right now, in our environment:
            # - Timeouts may result in nginx-created 500 Bad Gateway HTML being added to the response.
            # - Exceptions add some error json to the response, which is not SSE-sanitized.
            try:
                for item in report.collect():
                    try:
                        write(encoder.json_sse_pack({
                            'event': 'progress',
                            'data': item
                        }))
                    except Exception: # pylint: disable=broad-except
                        log.info('SSE upload progress failed to send; continuing')

                # Log last collection time
                time_since = datetime.datetime.now() - datetime.datetime(1970, 1, 1)
                values.LAST_REPORT_COLLECTION.labels(report_type).set(time_since.total_seconds())
            except Exception: # pylint: disable=broad-except
                log.exception('Error collecting %s report data', report_type)
                values.REPORT_COLLECTION_ERROR_COUNT.labels(report_type).inc()

            return ''

        return sse_handler

    def _get_report(self, report_type):
        """Get report for report_type and validate permissions"""
        if report_type in ReportTypes:
            report_class = ReportTypes[report_type]
            report = report_class(self.request.params)
        else:
            raise NotImplementedError('Report type {} is not supported'.format(report_type))

        if not self.superuser_request and not report.user_can_generate(self.uid):
            raise APIPermissionException('User {} does not have permissions to generate report'.format(self.uid))

        return report