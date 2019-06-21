"""Provides TreeHandler class"""
from ... import auth, validators
from ...web import base, errors

from ..graph import GRAPH
from ..tree_retrieval import TreeRetrieval

class TreeHandler(base.RequestHandler):
    """Build-your-own endpoint for list retrieval"""

    def get_graph(self):
        """Return the flywheel hierarchy graph (informational)"""
        return GRAPH

    @validators.verify_payload_exists
    @auth.require_privilege(auth.Privilege.is_user)
    def post(self):
        # Validate payload
        payload = self.request.json
        validators.validate_data(payload, 'tree-request.json', 'input', 'POST')

        # Set authorization
        uid = {'_id': self.uid} if not self.complete_list else None

        retrieval = TreeRetrieval(self.log)
        results = retrieval.retrieve(payload, self.pagination, uid)

        if not results:
            raise errors.APINotFoundException('No results found matching the request')

        return self.format_page(results)
