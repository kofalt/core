from .pipeline import PipelineStage, EndOfPayload

from ..access_logger import create_access_logger, is_phi_field
from ..util import is_nil, nil_value


class LogAccess(PipelineStage):
    """Performs access logging for each row collected from the Aggregate stage.

    Expects a single payload which is a list of rows generated from the Aggregate stage.
    Emits each row from the aggregate stage, followed by an EndOfPayload.
    """

    def __init__(self, config):
        super(LogAccess, self).__init__()
        self.config = config
        self.logger = create_access_logger()
        self.request = None
        self.origin = None

    def initialize(self, tree):
        """Initialize the access logger from config and the initial tree.

        Arguments:
            tree (list): The tree as retrieved via get_parent_tree
        """
        for col in self.config.columns:
            # Any subject fields and any info fields are considered PHI
            if is_phi_field(col.container, col.src):
                self.logger.add_container(col.container)

        if self.config.file_container:
            self.logger.set_file_container(self.config.file_container)

        self.logger.create_context(tree)

    def set_request_origin(self, request, origin):
        """Sets the request origin for the access logger, required before execution

        Arguments:
            request (object): The request object
            origin (dict): The request origin (e.g. the user initiating the request)
        """
        self.request = request
        self.origin = origin

    def process(self, payload):
        for row in payload:
            meta = row.pop("_meta")

            file_entry = row.get("file", nil_value)
            if not is_nil(file_entry):
                filename = file_entry["name"]
            else:
                filename = None

            self.logger.add_entries(meta, filename)

        # Write all of the access logs. If this fails, abort the request (allow exception to pass through)
        self.logger.write_logs(self.request, self.origin)

        # Now pass along each row, one at a time
        for row in payload:
            self.emit(row)

        self.emit(EndOfPayload)
