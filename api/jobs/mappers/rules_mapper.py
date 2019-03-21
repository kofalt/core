import bson

from ... import config
from ...web import errors
from ..models import Rule

class RulesMapper(object):
    """Data mapper for rules"""
    def __init__(self, db=None):
        self.db = db or config.db
        self.dbc = self.db.project_rules

    def insert(self, rule):
        """Insert a new rule

        Args:
            rule (Rule): The rule to insert

        Returns:
            ObjectId: the inserted rule id
        """
        result = self.dbc.insert_one(rule.to_dict())
        # Update the instance id if we didn't insert the rule with an id
        if rule.rule_id != result.inserted_id:
            rule.rule_id = result.inserted_id
        # Return the resulting id
        return result.inserted_id

    def patch(self, rule_id, doc):
        """Update a rule, with the given fields in the doc.

        Args:
            rule_id (str|ObjectId): The id of the rule to update
            doc (dict): The set of updates to apply

        Raises:
            APINotFoundException
        """
        # Create the update document
        update = {'$set': doc}
        response = self.dbc.update_one({'_id': bson.ObjectId(rule_id)}, update)
        if response.matched_count == 0:
            raise errors.APINotFoundException('Rule {} not found'.format(rule_id))


    def find_all(self, project_id=None, gear_id=None, fixed_input=None, auto_update=None,
                 disabled=None, projection=None):
        """Find all rules that satisfy a set of filters

        Args:
            project_id (str): An optional project id to filter rules on
            gear_id (str): An optional gear id to filter rules on
            fixed_input (dict): An optional file reference dictionary to filter rules on
            auto_update (bool): An optional value for auto_update to filter rules on
            disabled (bool): An optional value for disabled to filter rules on
            projection (dict): An optional dictionary that set fields to 1 or 0

        Yields:
            Rule: The next rule matching the given filters
        """
        # Build the query
        query = {
            'project_id': project_id,
            'gear_id': gear_id,
            'auto_update': auto_update,
            'disabled': disabled
        }
        query = {k: v for k, v in query.items() if v is not None}
        if fixed_input:
            query['fixed_inputs'] = {'$elemMatch': {'name': fixed_input['name'], 'id': fixed_input['id']}}
        config.log.debug('query is %s', query)
        # Build the projection from include or exclude
        # if include:
        #     projection = {field: 1 for field in include}
        # elif exclude:
        #     projection = {field: 0 for field in exclude}
        # else:
        #     projection = None

        if projection is not None:
            return self._find_all(query, projection=projection)
        else:
            return self._find_all(query)

    def _find_all(self, query, **kwargs):
        """Find all rules matching a query

        Args:
            query (dict): The query structure
            **kwargs: Additional args to pass to the find function

        Yields:
            Rule: The next rule matching the query
        """
        for rule_doc in self.dbc.find(query, **kwargs):
            yield self._load_rule(rule_doc)

    def get(self, rule_id, projection=None):
        """Find the rule that matches the given id.

        Args:
            rule_id (str|ObjectId): the id of the rule to find
            projection (dict): An optional dictionary that set fields to 1 or 0

        Returns:
            Rule: the loaded rule or None
        """
        result = self.dbc.find_one({'_id': bson.ObjectId(rule_id)}, projection=projection)
        return self._load_rule(result)

    def delete(self, rule_id):
        """Delete the rule with the given id

        Args:
            rule_id (str|ObjectId): The id of the rule to delete

        Returns:
            int: the number of deleted items
        """
        result = self.dbc.delete_one({'_id': bson.ObjectId(rule_id)})
        return result.deleted_count

    def _load_rule(self, rule_doc):
        """Loads a single rule document from mongo

        Args:
            rule_doc (dict): The rule document to load into a model

        Returns:
            Rule: The model from the given document
        """
        if rule_doc is None:
            return None

        return Rule.from_dict(rule_doc)

