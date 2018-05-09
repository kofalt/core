from .pipeline import PipelineStage, EndOfPayload

from ..access_logger import create_access_logger, is_phi_field

class LogAccess(PipelineStage):
    def __init__(self, config):
        super(LogAccess, self).__init__()
        self.config = config
        self.logger = create_access_logger()
        self.request = None
        self.origin = None

    def initialize(self, tree):
        for col in self.config.columns:
            # Any subject fields and any info fields are considered PHI
            if is_phi_field(col.container, col.src):
                next_part = col.src.split('.')[0]
                # TODO: Remove check when subject is formalized
                if next_part == 'subject':
                    self.logger.add_container('subject')
                else:
                    self.logger.add_container(col.container)
        
        if self.config.file_container:
            self.logger.set_file_container(self.config.file_container)

        self.logger.create_context(tree)

    def set_request_origin(self, request, origin):
        self.request = request
        self.origin = origin

    def process(self, rows):
        for row in rows:
            meta = row.pop('_meta')

            file_entry = row.get('file', None)
            if file_entry:
                filename = file_entry['name']
            else:
                filename = None

            self.logger.add_entries(meta, filename)

        # Write all of the access logs. If this fails, abort the request (allow exception to pass through)
        self.logger.write_logs(self.request, self.origin)

        # Now pass along each row, one at a time
        for row in rows:
            self.emit(row)

        self.emit(EndOfPayload)


