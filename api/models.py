"""Provides a base class for sparse models.

Example Usage:
    from .. import models

    class Container(models.Base):
        def __init__(self, label, public):
            self._id = None
            self.label = label
            self.public
"""
import collections

# NOTE: Python3 - str or bytes
STRING_TYPES = (str, unicode)


class Base(collections.MutableMapping):
    """Base class for sparse model classes.

    This model pattern supports setting and retrieving arbitrary
    attributes via the Mapping (dict) protocol. It also
    supports deleting arbitrary attributes.

    If any attribute is missing from the underlying document,
    None will be returned instead.
    """

    # pylint complains that we should invoke the non-exisitent MutableMapping.__init__
    def __init__(self):  # pylint: disable=super-init-not-called
        """Construct a new model."""
        pass

    @classmethod
    def from_dict(cls, dct):
        """Construct a model instance from a dictionary.

        Args:
            dct (dict): The dictionary to use
        """
        result = cls.__new__(cls)
        result.__dict__ = dct  # pylint: disable=attribute-defined-outside-init
        return result

    def to_dict(self):
        """Converts the model to a dictionary.

        The resulting model should be convertable to JSON or BSON

        Returns:
            dict: The converted model
        """
        return _model_to_dict(self.__dict__)

    def __contains__(self, key):
        return key in self.__dict__

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        del self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __getattr__(self, name):
        # NOTE: This is here to allow dot-access of named attributes
        # that have been removed or are missing from the underlying dict
        return None


def _model_to_dict(obj):
    """Flexible model conversion function
    Conversion is prioritized as follows:
        - Model subclasses are converted via to_dict
        - mappings (e.g dict or OrderedDict) are converted to dict
        - iterables (e.g. list or set) are converted to lists
        - Everything else is left as-is
    """
    if isinstance(obj, Base):
        return obj.to_dict()

    if isinstance(obj, collections.Mapping):
        result = {}
        for key, value in obj.iteritems():
            result[key] = _model_to_dict(value)
        return result

    if isinstance(obj, collections.Iterable) and not isinstance(obj, STRING_TYPES):
        result = []
        for value in obj:
            result.append(_model_to_dict(value))
        return result

    return obj
