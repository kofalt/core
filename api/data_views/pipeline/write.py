from .pipeline import PipelineStage, EndOfPayload


class Write(PipelineStage):
    """Terminal pipeline stage that writes rows to the given formatter.

    Expects flattened rows.
    Emits nothing.
    """

    def __init__(self, config, formatter):
        super(Write, self).__init__()
        self.config = config
        self.formatter = formatter

    def process(self, payload):
        if payload == EndOfPayload:
            self.formatter.finalize()
        else:
            self.formatter.write_row(payload, self.config.flat_columns)
