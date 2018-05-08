from .pipeline import PipelineStage, EndOfPayload
from ..util import is_nil, contains_nil

def get_missing_data_strategy(strategy):
    if not strategy or strategy == 'none':
        return ReplaceDataStrategy()
    if strategy == 'drop-row':
        return DropRowStrategy()
    raise ValueError('Unknown missing data strategy: {}'.format(strategy))

class DropRowStrategy(PipelineStage):
    """Missing value handler that will drop rows that are missing data"""
    def process(self, context):
        if context != EndOfPayload and contains_nil(context):
            return

        self.emit(context)

class ReplaceDataStrategy(PipelineStage):
    """Missing value handler that will replace missing data with the given value"""
    def __init__(self, value=None):
        super(ReplaceDataStrategy, self).__init__()
        self._replacement_value = value 

    def process(self, context): 
        if context != EndOfPayload:
            for key in context.keys():
                if is_nil(context[key]):
                    context[key] = self._replacement_value

        self.emit(context)

