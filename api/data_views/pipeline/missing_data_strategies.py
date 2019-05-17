from .pipeline import PipelineStage, EndOfPayload
from ..util import is_nil, contains_nil


def get_missing_data_strategy(strategy):
    if not strategy or strategy == "none":
        return ReplaceDataStrategy()
    if strategy == "drop-row":
        return DropRowStrategy()
    raise ValueError("Unknown missing data strategy: {}".format(strategy))


class DropRowStrategy(PipelineStage):
    """Missing value handler that will drop rows that are missing data

    Expects flattend rows.
    Emits flattened rows.
    """

    def process(self, payload):
        if payload != EndOfPayload and contains_nil(payload):
            return

        self.emit(payload)


class ReplaceDataStrategy(PipelineStage):
    """Missing value handler that will replace missing data with the given value

    Expects flattend rows.
    Emits flattened rows with nil_valueS replaced.
    """

    def __init__(self, value=None):
        super(ReplaceDataStrategy, self).__init__()
        self._replacement_value = value

    def process(self, payload):
        if payload != EndOfPayload:
            for key in payload.keys():
                if is_nil(payload[key]):
                    payload[key] = self._replacement_value

        self.emit(payload)
