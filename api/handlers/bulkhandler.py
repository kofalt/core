
import bson
import copy
import datetime
import dateutil

from .. import config

from ..auth import containerauth, always_ok
from ..dao import  containerutil
from ..dao.basecontainerstorage import ContainerStorage
from ..web import base
from ..web.errors import APIPermissionException, APIValidationException, InputValidationException
from ..web.request import log_access, AccessType


class BulkHandler(base.RequestHandler):
    """
    """

    def __init__(self, request=None, response=None):

        self.payload = request.json_body
        self.source_storage = None
        self.dest_storage = None
        self.source_list = None
        self.dest_list = None

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

        self.dest_storage = ContainerStorage.factory(self.payload['destination_container_type'])
        #self.dest_storage = getattr(containerstorage, containerutil.singularize(self.payload['destination_container_type']).capitalize() + 'Storage')()
        self.source_storage = ContainerStorage.factory(source_cont_name)
        #self.source_storage = getattr(containerstorage, containerutil.singularize(source_cont_name).capitalize() + 'Storage')()

        self.source_list = []
        self.dest_list = []
        if source_cont_name != 'groups':
            for _s in self.payload['sources']:
                self.source_list.append(bson.ObjectId(_s))
            for _d in self.payload['destinations']:
                self.dest_list.append(bson.ObjectId(_d))
        else:
            self.source_list = self.payload['sources']
            self.dest_list = self.payload(['destinations'])

        self._validate_inputs(source_cont_name)

        getattr(self, '_' + operation + '_' + source_cont_name + '_to_' + self.payload['destination_container_type'])()

    def _validate_inputs(self, source_cont):
        """
        Validate inputs are given and exist in the system
        """

        if not len(self.source_list):
            raise APIValidationException('You must provide at least one source')

        if not len(self.dest_list):
            raise APIValidationException('You must provide at least one destination')

        if len(self.source_list) > 1 and len(self.dest_list) > 1:
            raise APIValidationException('You can not specify multiple sources and destinations.')

        sources = self.source_storage.get_all_el(query={'_id': {'$in': self.source_list}},
            user=None, projection={'_id': 1})
        if len(sources) != len(self.source_list):
            source_set = set()
            for src in sources:
                source_set.add(src['_id'])
            missing = set(self.source_list) - source_set
            raise APIValidationException('The following sources are not valid: {}'.format(', '.join(str(s) for s in missing)))

        dests = self.dest_storage.get_all_el(query={'_id': {'$in': self.dest_list}},
            user=None, projection={'_id': 1})
        if len(dests) != len(self.dest_list):
            dest_set = set()
            for dst in dests:
                dest_set.add(dst['_id'])
            missing = set(self.dest_list) - dest_set
            print 'we have missing'
            print missing
            import sys
            sys.stdout.flush
            raise APIValidationException('The following destinations are not valid: {}'.format(', '.join(str(s) for s in missing)))


    def _move_sessions_to_projects(self):
        '''
        Requires a 2 phase approach.
        First is the dry run the second is with the conflict mode set

        For the matter of subjects existing they will have the same 'code'
        1. If the subject for the session in the source project does not exist in the destination project
            a. If the subject in the source project has more than one session
    		i. Copy the subject to the destination project and move the session to the copy
    	    b. If the subject in the source project session has just the session to be moved
    		i. Move the subject (with the session) to the destination project
        2. If the subject for the session in the source project does exist
            a. Raise an error (Conflict) on the dry run
    	    b. On the full run either move or skip
    		i. move the session to the subject in the destination but leave the subject in the source
    		ii. Or skip the move entirely.
        '''


        if (not self.payload.get('conflict_mode', False) or
                self.payload['conflict_mode'] is None or self.payload['conflict_mode'] == ''):
            return self.source_storage.move_sessions_to_project(self.source_list, self.dest_list[0], conflict_mode=self.payload.get('conflict_mode'))


        self.source_storage.move_sessions_to_project(self.source_list, self.dest_list[0], conflict_mode=self.payload.get('conflict_mode'))
        return True
