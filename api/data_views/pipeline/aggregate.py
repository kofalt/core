from .pipeline import PipelineStage

from ...dao import containerutil
from ...dao.basecontainerstorage import ContainerStorage
from ..hierarchy_aggregator import HierarchyAggregator, AggregationStage


class Aggregate(PipelineStage):
    """Performs the mongodb aggregation query for the selected containers.

    Expects the initial hierarchy tree as the payload.
    Emits a list of rows that were returned by the aggregation pipeline, combined with the initial context.

    The list of rows will have a _meta object that contains container labels and ids,
    and a list of analyses or files as configured in the pipeline.
    """

    def __init__(self, config):
        super(Aggregate, self).__init__()
        self.config = config

    def build_aggregator(self, tree):
        config = self.config

        cont_type = tree[-1]["cont_type"]
        cont_id = tree[-1]["_id"]

        # Determine the total depth
        aggregator = HierarchyAggregator()
        for dummy_idx in range(len(tree), len(config.containers)):
            child_cont_type = ContainerStorage.factory(cont_type).child_cont_name
            child_cont_type_singular = containerutil.singularize(child_cont_type)

            if not aggregator.stages:
                # Setup initial filtering
                key_name = containerutil.singularize(cont_type)
                aggregator.filter_spec = {key_name: cont_id}

            stage = AggregationStage(child_cont_type)
            for col in config.column_map.get(child_cont_type_singular, []):
                stage.fields.append(col.src)

            if child_cont_type_singular == config.file_container:
                # Check for analysis filter, if so we will load all of the analyses
                # for each row, which will include the files array
                if config.analysis_filter:
                    aggregator.stages.append(stage)

                    stage = AggregationStage("analyses", parent_key="parent.id", unwind=False)
                else:
                    stage.fields.append(("files", "files"))

            aggregator.stages.append(stage)

            # Advance cont_type
            cont_type = child_cont_type

        return aggregator

    def process(self, payload):
        # Build the initial context from payload
        context = {}
        for cont in payload:
            cont_type = containerutil.singularize(cont["cont_type"])
            context[cont_type] = cont

        # Start by building the pipeline
        aggregator = self.build_aggregator(payload)

        # Collect all of the rows as a single payload
        rows = []
        for row in aggregator.execute():
            row.update(context)
            rows.append(row)

        # Pass the full payload to the next stage
        # NOTE: We pass the rows all together because the access logger processes
        # and logs everything in bulk before passing to the next stage
        self.emit(rows)
