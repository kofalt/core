from .pipeline import PipelineStage, EndOfPayload

class Write(PipelineStage):
    def __init__(self, config, formatter):
        super(Write, self).__init__()
        self.config = config
        self.formatter = formatter

    def process(self, row):
        if row == EndOfPayload:
            self.formatter.finalize()
        else:
            self.formatter.write_row(row, self.config.flat_columns)

