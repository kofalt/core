from .pipeline import PipelineStage
from ..util import filtered_container_list, file_filter_to_regex

class MatchContainers(PipelineStage):
    def __init__(self, collection_key, name_key, output_key, filter_spec, match_type):
        super(MatchContainers, self).__init__()

        self.collection_key = collection_key
        self.name_key = name_key
        self.output_key = output_key
        self.filter_regex = file_filter_to_regex(filter_spec)
        self.match_type = match_type

    def match_files(self, files):
        # Find a matching, not-deleted file
        if files is not None:
            for f in files:
                if 'deleted' in f:
                    continue
                if self.file_filter.match(f['name']):
                    yield f

    def process(self, payload):
        # Keep unmatched values at the end
        rows = []
        unmatched = []

        # Pop and filter the containers from payload
        for row in payload:
            containers = row.pop(self.collection_key, [])
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

