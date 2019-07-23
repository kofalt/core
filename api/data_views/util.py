import collections
import fnmatch
import re

from ..web.errors import InputValidationException

def filtered_container_list(containers, filters, match_type='first', date_key='created'):
    """Return a list of matching, non_deleted containers from the input list.

    This function assumes that in addition to the label key, there is a 'created' key which will be used for sorting.

    Arguments:
        containers (list): The list of containers to sort and filter
        filters (list): The list of key-value pairs that must match
        match_type (string): The match type, one of: first, last, newest, oldest, all (defaults to first)
        date_key (string): The optional key to use for sorting (defaults to 'created')

    Returns:
        list: The list of matching containers (could be empty)
    """
    if filters is None:
        filters = []

    # Filter
    def match_fn(entry):
        # Ignore deleted entries
        if 'deleted' in entry:
            return False

        for filter_key, filter_pattern in filters:
            value = extract_json_property(filter_key, entry, '')
            if not filter_pattern.match(value):
                return False
            
        return True

    results = filter(match_fn, containers)

    # Sort
    if match_type == 'last':
        results = reversed(results)
    elif match_type == 'newest':
        sorted(results, key=lambda x: x[date_key], reverse=True)
    elif match_type == 'oldest':
        sorted(results, key=lambda x: x[date_key])

    # Reduce
    results = list(results)
    if match_type != 'all':
        results = results[:1]
    return results


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

def convert_to_datatype(value, datatype):
    """Attempt to convert value to the given datatype. 
    
    If conversion fails, returns nil_value.
    
    Arguments:
        value: The original value
        datatype: The datatype, one of string, int, float, bool

    Returns:
        The converted value, or nil_value if conversion failed.
    """
    if is_nil(value):
        return value

    try:
        if datatype == 'int':
            if value is None:
                return nil_value
            return int(value)
        elif datatype == 'float':
            return float(value)
        elif datatype == 'bool':
            if isinstance(value, basestring) and value.lower() == 'false':
                return False
            return bool(value)
        elif datatype == 'string':
            if value is None:
                return ''
            return str(value)
        elif datatype == 'object':
            return value
        else:
            raise RuntimeError('Unknown datatype: {}'.format(datatype))

    except ValueError:
        return nil_value
    except TypeError:
        return nil_value

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

nil_value = object()

def is_nil(val):
    """Check if the given value is nil"""
    return nil_value == val

def contains_nil(obj, nil_hint=False):
    """Check if the given dict contains any nil_value sentinal values"""
    if nil_hint:
        return True

    for val in obj.itervalues():
        if is_nil(val):
            return True

    return False

def deep_keys(obj, keys=None, prefix=None):
    """Get the set of all flattened keys in an object

    Arguments:
        obj (dict): The dictionary to query

    Returns:
        set: The set of all keys
    """
    if keys is None:
        keys = set()

    if isinstance(obj, dict):
        if prefix is None:
            prefix = ''

        for key, value in obj.items():
            deep_key = prefix + key
            if isinstance(value, dict):
                deep_keys(value, keys=keys, prefix=(deep_key+'.'))
            else:
                keys.add(deep_key)

    return keys 

