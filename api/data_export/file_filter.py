"""Provides utility functions for filtering container file lists"""


def filtered_files(container, filters):
    """Get a set of files on the given container that match the given filters.

    Returns the file group (i.e. input or output) as well as the file entry.

    Args:
        container (dict): The container to extract files from
        filters (list): The set of filters to match against

    Return:
        list(str, dict): The list of files that matched the filter
    """
    inputs = [("input", f) for f in container.get("inputs", [])]
    outputs = [("output", f) for f in container.get("files", []) if not f.get("deleted")]
    result = []
    for file_group, f in inputs + outputs:
        if filters:
            included = False
            for filter_ in filters:
                type_as_list = [f["type"]] if f.get("type") else []
                if file_filter_check(filter_.get("tags", {}), f.get("tags", [])) and file_filter_check(filter_.get("types", {}), type_as_list):
                    included = True
                    break
        else:
            included = True

        if included:
            result.append((file_group, f))

    return result


def file_filter_check(property_filter, property_values):
    """Check if the given property values pass the filter.

    Property filters are a map of plus(+) or minus(-) to a list of values.
    A filter passes if any of the values in the plus field are present, and
    none of the values in the minus field are present.

    In addition, the special value of null checks whether or not the property values
    are populated at all.

    Args:
        property_filter (dict): The property filter
        property_values (list): The set of property values to test against

    Returns:
        bool: True if the the file should be included based on property values.
    """
    minus = set(property_filter.get("-", []) + property_filter.get("minus", []))
    plus = set(property_filter.get("+", []) + property_filter.get("plus", []))
    if "null" in plus and not property_values:
        return True
    if "null" in minus and property_values:
        return False
    elif not minus.isdisjoint(property_values):
        return False
    if plus and plus.isdisjoint(property_values):
        return False
    return True
