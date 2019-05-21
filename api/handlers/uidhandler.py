"""Provides UID-related API Endpoint handling"""
from ..auth import require_login
from ..dao import containerstorage
from ..web import base
from .. import validators

class UIDHandler(base.RequestHandler):
    """API Handler for Checking for UID existence"""

    @require_login
    @validators.verify_payload_exists
    def check_uids(self):
        """Check if any of the given list of UIDs exist in the system"""
        payload = self.request.json_body
        validators.validate_data(payload, 'uidcheck-input.json', 'input', 'POST')

        result = {}
        for container_name in ('sessions', 'acquisitions'):
            # We can check sessions and acquisitions, return results for each
            uid_set = payload.get(container_name, [])
            if uid_set:
                uid_result = UIDHandler.check_uids_in_container(container_name, uid_set)
            else:
                uid_result = []
            result[container_name] = uid_result

        return result

    @staticmethod
    def check_uids_in_container(container_name, uid_set):
        """Check container_name for occurrences of the given set of uids.

        Args:
            container_name (str): The name of the container
            uid_set (list): The set of UIDs to search for

        Returns:
            list: The set of UIDs that were found
        """
        storage = containerstorage.cs_factory(container_name)

        query = {'uid': {'$in': uid_set}, 'deleted': {'$exists': False}}
        return list(storage.dbc.distinct('uid', filter=query))
