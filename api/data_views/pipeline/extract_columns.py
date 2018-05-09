from .pipeline import PipelineStage, EndOfPayload
from ..util import extract_json_property, nil_value, convert_to_datatype

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

                for col in column_map[cont_type]:
                    value = extract_json_property(col.src, cont, default=nil_value)
                    if col.datatype is not None:
                        value = convert_to_datatype(value, col.datatype)
                    row[col.dst] = value


            self.emit(row)

    
