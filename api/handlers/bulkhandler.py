
import bson
import copy
import datetime
import dateutil

from ..api import config

from ..auth import containerauth, always_ok
from ..dao import containerstorage, containerutil
from ..dao.containerstorage import AnalysisStorage
from ..web import base
from ..web.errors import APIPermissionException, APIValidationException, InputValidationException
from ..web.request import log_access, AccessType


class BulkHandler(base.RequestHandler):
    """
    """

    def __init__(self, request=None, response=None):

        self.payload = request.json_body
        self.source_storage = None
        self.dest_stroage = None

        super(BulkHandler, self).__init__(request, response)

    def bulk(self, operation, source_cont_name, **kwargs):
        """Entry point for the bulk operations"""


        # TODO: perform some permission checks first
        #permchecker = self._get_permchecker(container)
        # This line exec the actual get checking permissions using the decorator permchecker
        #result = permchecker(self.storage.exec_op)('GET', _id)
        #if result is None:
        #    self.abort(404, 'Element not found in container {} {}'.format(self.storage.cont_name, _id))
        #if not self.user_is_admin and not self.is_true('join_avatars'):
        #    self._filter_permissions(result, self.uid)

        print ('we are hitting it', operation, source_cont_name, self.payload)

        self.dest_storage = getattr(containerstorage, containerutil.singularize(self.payload['destination_container_type']).capitalize() + 'Storage')()
        self.source_storage = getattr(containerstorage, containerutil.singularize(source_cont_name).capitalize() + 'Storage')()
        self._validate_inputs(source_cont_name) 

        getattr(self, '_' + operation + '_' + source_cont_name)()

    def _validate_inputs(self, source_cont):
        """
        Validate inputs are given and exist in the system
        """

        if not len(self.payload['sources']):
            raise APIValidationException('You must provide at least one source')

        if not len(self.payload['destinations']):
            raise APIValidationException('You must provide at least one destination')

        if len(self.payload['sources']) > 1 and len(self.payload['destinations']) > 1:
            raise APIValidationException('You can not specify multiple sources and destinations.')

        sources = self.source_storage.get_all_el(query={'_id': {'$in': self.payload['sources']}}, user=None, projection={'_id': 1})
        if len(sources) != len(self.payload['sources']):
            missing = set(self.payload['sources']) - set(sources)
            raise APIValidationException('The following sources are not valid: {}'.format(', '.join(str(s) for s in missing)))

        dests = self.dest_storage.get_all_el(query={'_id': {'$in': self.payload['sources']}}, user=None, projection={'_id': 1})
        if len(sources) != len(self.payload['destinations']):
            missing = set(self.payload['destinations']) - set(dests)
            raise APIValidationException('The following destinations are not valid: {}'.format(', '.join(str(s) for s in missing)))


    def _move_sessions(self):

        # We move sessions to new project for now. Add dest of session later
        query = {}
        source_subject_codes = config.db.subjects.find_many(query, user=None, projection={'_id': 1, 'code': 1})

        conflicts = config.db.subjects.find_many({'_id': 'test'})

        # first we find conflicts as those are needed for dry run regardless.
        # Then we return that on dry run.

        # Next we need to find the two sets that are not conflicts
            # move: conflicts have more than one session in the source project
            # copy: subjects that have just the one session in the conflict  list


#        Requires a 2 phase approach.
#First is the dry run the second is with the action set to do it
#
#1. If the subject for the session in the source project does not exist in the destination project
#	a. If the subject in the source project has more than one session
#		i. Copy the subject to the destination project and move the session to the copy
#	b. If the subject in the source project session has just the session to be moved
#		i. Move the subject (with the session) to the destination project
#2. If the subject for the session in the source project does exist
#	a. Raise an error (Conflict) on the dry run
#	b. On the full run either move or skip
#		i. move the session to the subject in the destination but leave the subject in the source
#		ii. Or skip the move entirely.



