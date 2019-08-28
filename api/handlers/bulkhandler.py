import bson

from ..auth.containerauth import validate_container_permissions
from ..dao.basecontainerstorage import ContainerStorage
from ..web import base
from ..web.errors import APIPermissionException, APIValidationException
from ..validators import validate_data
from ..auth import require_privilege, Privilege

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

    @require_privilege(Privilege.is_user)
    def bulk(self, operation, source_cont_name):
        """Entry point for the bulk operations"""

        validate_data(self.payload, 'bulk.json', 'input', 'POST')

        method = '_{}_{}_to_{}'.format(operation, source_cont_name,
                                       self.payload['destination_container_type'])
        try:
            getattr(self, method)
        except AttributeError:
            self.abort(501, 'This method is not implemented yet')

        self.dest_storage = ContainerStorage.factory(self.payload['destination_container_type'])
        self.source_storage = ContainerStorage.factory(source_cont_name)

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

        if not self.user_is_admin:

            if not validate_container_permissions(
                    self.dest_list, self.payload['destination_container_type'], self.uid, 'rw'):
                raise APIPermissionException('You do not have sufficient permission on destination container')

            if not validate_container_permissions(self.source_list, source_cont_name, self.uid, 'ro'):
                raise APIPermissionException('You do not have read permission on all the source containers')

        self._validate_inputs()

        return getattr(self, method)()

    def _validate_inputs(self):
        """
        Validate inputs are given and exist in the system
        """

        if not self.source_list:
            raise APIValidationException('You must provide at least one source')

        if not self.dest_list:
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

        if (self.payload.get('conflict_mode') is None or self.payload['conflict_mode'] == ''):
            return self.source_storage.move_sessions_to_project(self.source_list, self.dest_list[0], conflict_mode=None)

        self.source_storage.move_sessions_to_project(self.source_list, self.dest_list[0], conflict_mode=self.payload.get('conflict_mode'))
        return True


    def _move_sessions_to_subjects(self):
        '''
        Moves all sessions in the soruce list to the destination project
        Subjects that do not exist in the destination will be copied
        Conflicts are not an issue so its just a bulk move to update pointers
        '''

        self.source_storage.move_sessions_to_subject(self.source_list, self.dest_list[0], conflict_mode=None)
        return True
