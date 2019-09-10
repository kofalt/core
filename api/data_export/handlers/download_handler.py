"""Provides handler class for downloads"""

from ... import io
from ...web import base, errors

from ..tar_download_writer import TarDownloadWriter
from ..download_file_source import DownloadFileSource
from ..strategy import create_download_strategy
from ..mappers import DownloadTickets

class DownloadHandler(base.RequestHandler):
    """Handler that implements download endpoints"""

    def get_strategy(self):
        """Get the DownloadStrategy instance, or raise an error if the strategy does not exist"""
        download_type = self.get_param('type')
        if download_type is None:
            # Fallback to legacy strategies
            download_type = 'bulk' if self.is_true('bulk') else 'classic'

        result = create_download_strategy(download_type, self.log, self.get_params())
        if result is None:
            raise errors.InputValidationException('Unknown download type: {}'.format(download_type))
        return result

    def download(self):
        """Download files or create a download ticket"""
        ticket_id = self.get_param('ticket')
        if ticket_id:
            tickets = DownloadTickets()
            ticket = tickets.get(ticket_id)

            # Ticket validation
            if not ticket:
                raise errors.APINotFoundException('No such download ticket')
            if ticket.ip != self.request.client_addr:
                raise errors.InputValidationException('Ticket not for this source IP')

            def response_handler(environ, start_response): # pylint: disable=unused-argument
                write = start_response('200 OK', [
                    ('Content-Type', 'application/octet-stream'),
                    ('Content-Disposition', 'attachment; filename="{}"'.format(
                        ticket.filename.encode('ascii', errors='ignore'))),
                    ('Connection', 'keep-alive')
                ])

                # Create the source
                source = DownloadFileSource(ticket, self.request)
                out = io.ResponseWriter(write)

                try:
                    writer = TarDownloadWriter(self.log, out)
                    writer.write(source)
                    writer.close()
                except Exception:  # pylint: disable=broad-except
                    # Bury exception and just truncate the response
                    self.log.exception('Error sending tarfile')

                return ''

            return response_handler
        else:
            strategy = self.get_strategy()

            req_spec = self.request.json_body
            strategy.validate_spec(req_spec, summary=False)

            # For authorization - no uid is required for admin user
            uid = None if self.user_is_admin else self.uid

            # Raises if no files are found
            return strategy.create_ticket(req_spec, uid, self.request.client_addr, self.origin)

    def summary(self):
        """Generate a download summary report"""
        strategy = self.get_strategy()

        req_spec = self.request.json_body
        strategy.validate_spec(req_spec, summary=True)

        # For authorization - no uid is required for admin user
        uid = None if self.user_is_admin else self.uid

        # Raises if no files are found
        return strategy.create_summary(req_spec, uid)


    def get_targets(self, ticket_id):
        """List all download targets of a ticket"""
        tickets = DownloadTickets()
        ticket = tickets.get(ticket_id)

        # Ticket validation
        if not ticket:
            raise errors.APINotFoundException('No such download ticket')
        if ticket.ip != self.request.client_addr:
            raise errors.InputValidationException('Ticket not for this source IP')

        # TODO consider long target lists:
        #  - enable filtering
        #  - split across multiple docs
        #  - stream multipart json
        return ticket.targets
