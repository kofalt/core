import collections
import fnmatch
import re

from ..web.errors import InputValidationException

def extract_json_property(name, obj, default=None):
    """Deeply extract a property from an object, using dot notation.

    List values can be extracted by specifying a numeric array index (starting from 0).

    Arguments:
        name (str): The name of the property to extract
        obj (dict,list): The object to extract a value from.
        default: The default value to return if the name cannot be resolved. (default is None)

    Returns:
        The extracted object, or default value if the property could not be found
    """
    path = name.split('.')
    for path_el in path:
        if isinstance(obj, collections.Sequence):
            try:
                obj = obj[int(path_el)]
            except IndexError:
                obj = nil_value 
            except ValueError:
                obj = nil_value 
        elif isinstance(obj, collections.Mapping):
            obj = obj.get(path_el, nil_value)
        else:
            obj = getattr(obj, path_el, nil_value)

        if is_nil(obj) or obj is None: 
            break

    if is_nil(obj):
        return default

    return obj

def file_filter_to_regex(filter_spec):
    """Convert a file-filter-spec to a regular expression

    Arguments:
        filter_spec (dict): The filter specification

    Returns:
        A compiled regular expression
    """        
    try:
        val = filter_spec['value']
        if not filter_spec.get('regex', False):
            val = fnmatch.translate(val)
        return re.compile(val, re.I)
    except re.error:
        raise InputValidationException('Invalid filter spec: {}'.format(filter_spec['value']))

class NilValue(object):
    """A sentinal value that represents missing data (semantically different from None)"""
    def __repr__(self):
        return 'nil'

nil_value = NilValue()

def is_nil(val):
    """Check if the given value is nil"""
    return isinstance(val, NilValue)

def contains_nil(obj, nil_hint=False):
    """Check if the given dict contains any nil_value sentinal values"""
    if nil_hint:
        return True

    for val in obj.itervalues():
        if is_nil(val):
            return True

    return False

