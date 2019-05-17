from .pipeline import PipelineStage, EndOfPayload
from ..util import deep_keys, extract_json_property, nil_value
from ..config import ColumnSpec


class DiscoverColumns(PipelineStage):
    """Pipeline stage that flattens columns. 

    Expects a list of rows. 
    Emits a list of rows.
    Updates the column configuration based on discovered columns
    """

    def __init__(self, config):
        super(DiscoverColumns, self).__init__()
        self.config = config
        self.processed = False

    def process(self, payload):
        # We only process the first row (like we do with files)
        if not self.processed and payload != EndOfPayload:
            # Discover dictionary objects for the first row
            flat_map = {}

            column_map = self.config.column_map
            for cont_type, cont in payload.items():
                if cont_type not in column_map:
                    continue

                for col in column_map[cont_type]:
                    # Extract the json value, and check for dictionary
                    value = extract_json_property(col.src, cont, default=nil_value)
                    if isinstance(value, dict):
                        # Extract the deep keys
                        flat_map[col] = deep_keys(value, prefix=(col.src + "."))

            for col, src_cols in flat_map.items():
                # Map to new ColumnSpec objects under destination name
                replacements = []
                src_len = len(col.src)

                for src in src_cols:
                    dst = col.dst + src[src_len:]
                    replacements.append(ColumnSpec(col.container, src, dst))

                # Replace the original column
                self.config.replace_column(col, replacements)

            self.processed = True

        self.emit(payload)
