from ..web import base
from ..reports import ReportTypes
from ..web.request import AccessTypeList

class ReportHandler(base.RequestHandler):
    """Handles report requests

    To add a new report, declare a subclass of Report,
    and add it to the ReportTypes map in __init__.py
    """
    def get_types(self):
        return AccessTypeList

    def get(self, report_type):

        report = None

        if report_type in ReportTypes:
            report_class = ReportTypes[report_type]
            report = report_class(self.request.params)
        else:
            raise NotImplementedError('Report type {} is not supported'.format(report_type))

        if report.user_can_generate(self.uid, self.roles):
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
        else:
            self.abort(403, 'User {} does not have required permissions to generate report'.format(self.uid))
