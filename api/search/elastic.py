"""Module that converts FlyQL AST to Elastic Queries"""
import re

from . import ast


# Type conversion regular expressions
RE_BOOL = re.compile(r"^(true|false)$")
RE_INTEGER = re.compile(r"^-?\d+$")
RE_DECIMAL = re.compile(r"^-?\d+\.\d+$")

_OPT_FRACTION = r"([\.,]\d+)?"  # Optional fractional seconds
_OPT_OFFSET = r"(Z|([+-]\d{2}:\d{2}))?"  # Optional timezone offset Z or [-+]HH:MM

# Date with optional timestamp
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}" + _OPT_FRACTION + _OPT_OFFSET + ")?$")


def to_es_query(tree):
    """Convert the given syntax tree to an elastic query.

    Args:
        tree (object): The root of the syntax tree, e.g. a Term or Expression

    Returns:
        dict: The elastic query generated from the syntax tree.
    """
    result = handle_node(tree)
    if "bool" not in result:
        result = _wrap_must(result)
    return result


def handle_term(term):
    """"Convert a search Term to an elastic query clause.

    Args:
        term (ast.Term): The search term

    Returns:
        dict: The converted term
    """
    return handle_op(term.op, term.field, term.phrase)


def handle_group(group):
    """"Convert a grouped expression to an elastic query.

    Args:
        group (ast.Group): The grouped search expression

    Returns:
        dict: The converted term
    """
    return handle_node(group.expr)


def handle_not(op):
    """"Convert a negated expression to an elastic query.

    Args:
        op (ast.Not): The negated search expression

    Returns:
        dict: The converted term
    """
    return _wrap_must_not(handle_node(op.expr))


def handle_and(op):
    """"Convert ANDed expressions to an elastic query.

    Args:
        op (ast.And): The search expressions

    Returns:
        dict: The converted term
    """
    return {"bool": {"must": [handle_node(op.lhs), handle_node(op.rhs)]}}


def handle_or(op):
    """"Convert ORed expressions to an elastic query.

    Args:
        op (ast.OR): The search expressions

    Returns:
        dict: The converted term
    """
    return {"bool": {"should": [handle_node(op.lhs), handle_node(op.rhs)]}}


def handle_op(op, field, value):
    """Convert the given operation to an elastic search term.

    This will look at the operation and value to determine if we're searching
    against a raw field or an analyzed field.

    Returns an elastic term which can be further wrapped in bool expressions.

    Args:
        op (str): The operation string (e.g. '==' or 'LIKE')
        field (TermStr): The name of the field being searched.
        value (TermStr): The basis for comparison.

    Returns:
        dict: The converted term
    """
    raw_field = "{}.raw".format(field)

    if op == "==" or op == "=":
        picked_field, value = _convert_term(value, field, raw_field)
        return {"term": {picked_field: value}}
    if op == "!=" or op == "<>":
        picked_field, value = _convert_term(value, field, raw_field)
        return _wrap_must_not({"term": {picked_field: value}})
    if op == "<":
        picked_field, value = _convert_term(value, field, raw_field)
        return {"range": {picked_field: {"lt": value}}}
    if op == "<=":
        picked_field, value = _convert_term(value, field, raw_field)
        return {"range": {picked_field: {"lte": value}}}
    if op == ">":
        picked_field, value = _convert_term(value, field, raw_field)
        return {"range": {picked_field: {"gt": value}}}
    if op == ">=":
        picked_field, value = _convert_term(value, field, raw_field)
        return {"range": {picked_field: {"gte": value}}}
    if op == "in":
        return {"terms": {raw_field: value}}
    if op == "like":
        # Convert from SQL-like to elastic wildcard
        value = value.replace("%", "*").replace("_", "?")
        return {"wildcard": {raw_field: value}}
    if op == "contains":
        return {"match": {field: value}}
    if op == "exists":
        return {"exists": {"field": field}}
    if op == "=~":
        return {"regexp": {raw_field: value}}
    if op == "!~":
        return _wrap_must_not({"regexp": {raw_field: value}})

    raise RuntimeError("Unknown operator: {}".format(op))


def _wrap_must_not(expr):
    """Helper function to negate a bool expression"""
    return {"bool": {"must_not": [expr]}}


def _wrap_must(expr):
    """Helper frunction to wrap a bool expression in a MUST term"""
    return {"bool": {"must": [expr]}}


def _convert_term(value, field, raw_field):
    """Convert the given value to a primitive type.

    This function takes a value, field and raw_field and returns a tuple of
    (selected_field, converted_value) where selected_field is either field or
    raw_field, depending on whether the value is quoted or converted. converted_value
    will either be a primitive or a string, depending on whether it's quoted or
    convertible to a primitive.

    For primitive fields, there won't be a raw field, so we should use the
    normal field name. For string values, we should be comparing against the
    raw field, rather than the analyzed field.
    """
    if getattr(value, "token_type", "id") == "quoted":
        return (raw_field, value)

    # Check against least to most specific regex
    if RE_BOOL.match(value):
        return (field, value == "true")
    if RE_INTEGER.match(value):
        return (field, int(value))
    if RE_DECIMAL.match(value):
        return (field, float(value))
    if RE_DATE.match(value):
        return (field, value)

    return (raw_field, value)


# Dispatch map of node class to handler function
HANDLER_MAP = {ast.Term: handle_term, ast.Group: handle_group, ast.Not: handle_not, ast.And: handle_and, ast.Or: handle_or}


def handle_node(node):
    """Handle conversion of any node type by dispatching to the correct handler.

    Args:
        node (object): The node to be converted

    Returns:
        dict: The elastic query generated from the syntax tree.
    """
    node_type = type(node)

    handler = HANDLER_MAP.get(node_type)
    if handler is None:
        raise RuntimeError("Unknown node type: {}".format(node_type.__name__))

    return handler(node)
