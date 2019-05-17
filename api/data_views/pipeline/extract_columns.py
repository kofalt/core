from .pipeline import PipelineStage, EndOfPayload
from ..util import extract_json_property, nil_value, convert_to_datatype


class ExtractColumns(PipelineStage):
    """Pipeline stage that extracts values from a context into a flattened row.

    Expects a single row (the input context).
    Emits a single row of flattened values
    """

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
                    # Extract the json property
                    value = extract_json_property(col.src, cont, default=nil_value)

                    # Apply expression, if specified
                    if value != nil_value and col.expr is not None:
                        # Expression has been validated, shouldn't encounter errors
                        value = col.expr.eval({"x": value})

                    # Convert the property, if a datatype was specified
                    if col.datatype is not None:
                        value = convert_to_datatype(value, col.datatype)
                    # Add to the flattened row
                    row[col.dst] = value

            self.emit(row)
