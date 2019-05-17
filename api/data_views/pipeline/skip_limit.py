import sys
from .pipeline import PipelineStage, EndOfPayload


class SkipAndLimit(PipelineStage):
    """Pipeline stage that limits the number of values returned

    Expects a single row
    Emits a single row
    """

    def __init__(self, pagination):
        super(SkipAndLimit, self).__init__()
        self.limit = pagination.get("limit", sys.maxint)
        self.skip = pagination.get("skip", 0)

    def process(self, payload):
        if payload == EndOfPayload:
            self.emit(payload)
        elif self.skip > 0:
            # Skip while the skip count is positive
            self.skip -= 1
        elif self.limit > 0:
            # Emit while limit is positive
            self.emit(payload)
            self.limit -= 1
