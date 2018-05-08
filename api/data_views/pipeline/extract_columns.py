from .pipeline import PipelineStage, EndOfPayload
from ..util import extract_json_property, nil_value

class ExtractColumns(PipelineStage):
    def __init__(self, config):
        super(ExtractColumns, self).__init__()
        self.config = config

    def process(self, payload):
        if payload == EndOfPayload:
            self.emit(payload)
        else:
            column_map = self.config.column_map

            row = {}
            for cont_type, cont in payload.items():
                if cont_type not in column_map:
                    continue

                for src, dst in column_map[cont_type]:
                    row[dst] = extract_json_property(src, cont, default=nil_value)

            self.emit(row)

    
