from .pipeline import PipelineStage
from ..util import filtered_container_list, file_filter_to_regex

def pop_collection(cont, key):
    result = []
    parts = key.split('.')

    for part in parts[:-1]:
        cont = cont.get(part)
        if not cont:
            break

    if cont:
        result = cont.pop(parts[-1], [])

    return result

class MatchContainers(PipelineStage):
    def __init__(self, collection_key, name_key, output_key, filter_spec, match_type):
        super(MatchContainers, self).__init__()

        self.collection_key = collection_key
        self.name_key = name_key
        self.output_key = output_key
        self.filter_regex = file_filter_to_regex(filter_spec)
        self.match_type = match_type

    def process(self, payload):
        # Keep unmatched values at the end
        rows = []
        unmatched = []

        # Pop and filter the containers from payload
        for row in payload:
            containers = pop_collection(row, self.collection_key)
            containers = filtered_container_list(containers, self.name_key, self.filter_regex, self.match_type)

            if containers:
                # Emit one row per match
                for entry in containers:
                    new_row = row.copy()
                    new_row[self.output_key] = entry 
                    rows.append(new_row)
            else:
                unmatched.append(row)

        self.emit(rows + unmatched)

