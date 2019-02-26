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

    # TODO: Remove this property once native support in no-root lands
    @property
    def complete_list(self):
        if self.is_true('root') or self.is_true('exhaustive'):
            if self.user_is_admin:
                return True
            raise errors.APIPermissionException('User {} is not authorized to request complete lists'.format(self.uid))
        return False

    @validators.verify_payload_exists
    @auth.require_login
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
