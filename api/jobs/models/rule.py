from ... import models
from copy import deepcopy

class Rule(models.Base):
    """Represents a a site or project gear rule"""
    def __init__(self, gear_id, name, any_, all_, not_,
                 project_id=None, config=None, fixed_inputs=None,
                 auto_update=False, disabled=False):
        """Create a new gear rule.

        Args:
            gear_id (str): The id of the gear to run when rule conditions are matched
            name (str): The name of the rule
            any_ (list): The list of conditions where any one must be met to trigger the gear
            all_ (list): The list of conditions where all must be met to trigger the gear
            not_ (list): The list of conditions that must not be met to trigger the gear
            project_id (str): The id of the project that the rule will run on, (site is a valid value)
            config (dict): The optional configuration to set when the job is created
            fixed_inputs (list): The optional list of files to set for inputs on multi-input gears
            auto_update (bool): The optional setting to automatically update the gear to the latest version, this is not valid when config or fixed_inputs are set.
            disabled (bool): The optional setting to disable a rule from triggering jobs
        """
        super(Rule, self).__init__()

        self.gear_id = gear_id
        """str: The id of the gear to run when rule conditions are matched"""

        self.name = name
        """str: The name of the rule"""

        self.any_ = any_
        """str: The list of conditions where any one must be met to trigger the gear"""

        self.all_ = all_
        """str: The list of conditions where all must be met to trigger the gear"""

        self.not_ = not_
        """str: The list of conditions that must not be met to trigger the gear"""

        self.project_id = project_id
        """str: The id of the project that the rule will run on, (site is a valid value)"""

        self.config = config
        """dict: The optional configuration to set when the job is created"""

        self.fixed_inputs = fixed_inputs
        """list: The optional list of files to set for inputs on multi-input gears"""

        self.auto_update = auto_update
        """bool: The optional setting to automatically update the gear to the latest version, this is not valid when config or fixed_inputs are set"""

        self.disabled = disabled
        """bool: The optional setting to disable a rule from triggering jobs"""

        self._id = None
        """ObjectId: The id of the rule"""

    @property
    def rule_id(self):
        return self._id

    @rule_id.setter
    def rule_id(self, _id):
        if self._id is not None:
            raise ValueError('Cannot set _id if it has already been set!')
        self._id = _id

    def copy(self):
        """Returns a copy of the rule without the id set

        Returns:
            Rule: a deep copy of self without the id set
        """
        rule_doc = deepcopy(self.to_dict())
        rule_doc.pop('_id', None)
        rule = Rule.from_dict(rule_doc)
        return rule

    @classmethod
    def from_dict(cls, dct):
        """Construct a model instance from a dictionary.

        Args:
            dct (dict): The dictionary to use

        Returns:
            Rule: The the rule model created from the given dictionary
        """
        dct = deepcopy(dct)

        # Modify the 'any', 'all', and 'not' fields to the attribute names
        # But only if they exist
        conditions = {}
        conditions['not_'] = dct.pop('not', None)
        conditions['any_'] = dct.pop('any', None)
        conditions['all_'] = dct.pop('all', None)

        conditions = {k: v for k, v in conditions.items() if v is not None}
        dct.update(conditions)

        dct['auto_update'] = bool(dct.get('auto_update'))
        dct['disabled'] = bool(dct.get('disabled'))
        return super(Rule, cls).from_dict(dct)

    def to_dict(self):
        """Converts the model to a dictionary.

        The resulting model should be convertable to JSON or BSON.

        The 'any_', 'all_', and 'not_' attriubutes are replaced with
        'any', 'all', and 'not' respectively.

        Returns:
            dict: The converted model
        """
        dct = super(Rule, self).to_dict()

        # Modify the 'any_', 'all_', and 'not_' attriubutes to the field names
        # But only if they exist
        conditions = {}
        conditions['not'] = dct.pop('not_', None)
        conditions['any'] = dct.pop('any_', None)
        conditions['all'] = dct.pop('all_', None)

        conditions = {k: v for k, v in conditions.items() if v is not None}
        dct.update(conditions)
        return dct

