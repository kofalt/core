import bson
import datetime
import re

from .pipeline import PipelineStage, EndOfPayload
from ...util import datetime_from_str


class Filter(PipelineStage):
    """Filter stage for pipeline, filters out rows that don't match the filter spec

    Expects a single flat row.
    Emits a single row
    """

    def __init__(self, filter_spec):
        """Initialize the pipeline stage, with the filter spec from pagination.

        Arguments:
            filter_spec (dict): The filter spec
                e.g. {'filter': {u'subject.code': {'$eq': 1001.0}}}
        """
        super(Filter, self).__init__()

        self.filters = []
        for key, spec in filter_spec.items():
            op = spec.keys()[0]
            value = spec[op]

            self.filters.append(make_filter_fn(key, op, value))

    def process(self, payload):
        if payload == EndOfPayload:
            self.emit(payload)
            return

        for filter_fn in self.filters:
            if not filter_fn(payload):
                return

        self.emit(payload)


def make_filter_fn(key, op, value):
    """Create a filter function that checks the value of key in context against value.

    Arguments:
        key (str): The key to extract
        op (str): The operation (e.g. $lt)
        value: The value to compare against
    """
    compare_fn_name = "compare_fn_{}".format(op.lstrip("$"))
    if compare_fn_name not in globals():
        # If this is encountered, it's probably because a new filter operation was added to pagination
        raise RuntimeError("Invalid filter operation: {}".format(op))
    if op == "$regex":
        value = re.compile(value)
    compare_fn = globals()[compare_fn_name](value)

    # Type coercion for value type
    coerce_fn = get_coerce_fn(type(value))

    key = "_filter.{}".format(key)

    def filter_fn(context):
        rhs = coerce_fn(context.pop(key, None))
        return compare_fn(rhs)

    return filter_fn


def compare_fn_lt(rhs):
    """Compare lhs < rhs"""
    return lambda lhs: lhs < rhs


def compare_fn_lte(rhs):
    """Compare lhs <= rhs"""
    return lambda lhs: lhs <= rhs


def compare_fn_eq(rhs):
    """Compare lhs == rhs"""

    def equal_or_in(lhs):
        if isinstance(lhs, list):
            return rhs in lhs
        return lhs == rhs

    return equal_or_in


def compare_fn_ne(rhs):
    """Compare lhs != rhs"""

    def not_equal_or_in(lhs):
        if isinstance(lhs, list):
            return rhs not in lhs
        return lhs != rhs

    return not_equal_or_in


def compare_fn_gte(rhs):
    """Compare lhs >= rhs"""
    return lambda lhs: lhs >= rhs


def compare_fn_gt(rhs):
    """Compare lhs > rhs"""
    return lambda lhs: lhs > rhs


def compare_fn_regex(rhs):
    """Check that regex matches"""
    return lambda lhs: bool(rhs.match(lhs))


def get_coerce_fn(cls):
    """Get a function that coerces values into the given type"""
    if cls == bson.ObjectId:
        return coerce_objectid
    if cls == float:
        return coerce_float
    if cls == datetime.datetime:
        return coerce_datetime
    if cls == str or cls == unicode or cls == re._pattern_type:  # pylint: disable=protected-access
        return coerce_str
    # pylint: disable=unnecessary-lambda
    return lambda x: x


def coerce_float(value):
    """Attempt to coerce value to a float"""
    if isinstance(value, list):
        return [safe_float(x) for x in value]
    return safe_float(value)


def coerce_datetime(value):
    """Attempt to coerce value to a datetime"""
    if isinstance(value, datetime.datetime):
        return value
    return datetime_from_str(str(value)) or value


def coerce_objectid(value):
    """Attempt to coerce value to an ObjectId"""
    if bson.ObjectId.is_valid(value):
        return bson.ObjectId(value)
    return value


def coerce_str(value):
    """Attempt to coerce value to a str"""
    if isinstance(value, list):
        return [str(x) for x in value]
    return str(value)


def safe_float(value):
    """Safely try to convert val to float"""
    try:
        return float(value)
    except ValueError:
        return value
