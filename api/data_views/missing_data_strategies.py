from .util import is_nil, contains_nil

def get_missing_data_strategy(strategy, formatter):
    if not strategy or strategy == 'none':
        return ReplaceDataStrategy(formatter)
    if strategy == 'drop-row':
        return DropRowStrategy(formatter)
    raise ValueError('Unknown missing data strategy: {}'.format(strategy))

class DropRowStrategy(object):
    """Missing value handler that will drop rows that are missing data"""
    def __init__(self, formatter):
        self._formatter = formatter

    def write_row(self, context, columns, nil_hint=False):
        if contains_nil(context, nil_hint):
            return

        self._formatter.write_row(context, columns)

class ReplaceDataStrategy(object):
    """Missing value handler that will replace missing data with the given value"""
    def __init__(self, formatter, value=None):
        self._formatter = formatter
        self._replacement_value = value 

    def write_row(self, context, columns, nil_hint=False): # pylint: disable=unused-argument
        for key in context.keys():
            if is_nil(context[key]):
                context[key] = self._replacement_value

        self._formatter.write_row(context, columns)

