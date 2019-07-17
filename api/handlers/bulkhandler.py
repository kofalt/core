
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

        self.dest_storage = ContainerStorage.factory(self.payload['destionation_container_type'])
        #self.dest_storage = getattr(containerstorage, containerutil.singularize(self.payload['destination_container_type']).capitalize() + 'Storage')()
        self.source_storage = ContainerStorage.factory(source_cont_name)
        #self.source_storage = getattr(containerstorage, containerutil.singularize(source_cont_name).capitalize() + 'Storage')()

        self.source_list = []
        self.dest_list = []
        if source_cont_name != 'groups':
            for _s in self.payload['sources']:
                self.source_list.append(bson.ObjectId(_s['_id']))
            for _d in self.payload['destinations']:
                self.dest_list.append(bson.ObjectId(_d['_id']))
        else:
            self.source_list = self.payload['sources']
            self.dest_list = self.payload(['destinations'])

        self._validate_inputs(source_cont_name, source_list, dest_list)

        getattr(self, '_' + operation + '_' + source_cont_name + '_to_' + dest_cont_name)()

    def _validate_inputs(self, source_cont, source_list, dest_list):
        """
        Validate inputs are given and exist in the system
        """

        if not len(source_list):
            raise APIValidationException('You must provide at least one source')

        if not len(dest_list):
            raise APIValidationException('You must provide at least one destination')

        if len(source_list) > 1 and len(dest_list) > 1:
            raise APIValidationException('You can not specify multiple sources and destinations.')

        sources = self.source_storage.get_all_el(query={'_id': {'$in': source_list}},
                user=None, projection={'_id': 1})

        print len(sources)
        print sources
        import sys
        sys.stdout.flush()

        if len(sources) != len(self.payload['sources']):
            missing = set(self.payload['sources']) - set(sources)
            raise APIValidationException('The following sources are not valid: {}'.format(', '.join(str(s) for s in missing)))

        dests = self.dest_storage.get_all_el(query={'_id': {'$in': self.payload['destinations']}}, user=None, projection={'_id': 1})
        if len(sources) != len(self.payload['destinations']):
            missing = set(self.payload['destinations']) - set(dests)
            raise APIValidationException('The following destinations are not valid: {}'.format(', '.join(str(s) for s in missing)))


    def _move_sessions_to_projects(self):

        # TODO: Do we assume all sessions come from the same project?
        # IF so we need to validate this.  
        # If not we need to group the sessions by project and loop over the groups
        source_session = self.dest_storage.get_el(payload['destinations'][0])
        source_project = source_subject['project']

        # Find all the source subjects first.
        source_subjects = config.db.sessions.aggregate([
            {'project': source_project, '_id': {'$in': self.payload['sources']}},
            {'$lookup': {
                'subjects',
                'subject',
                '_id',
                'subject_doc'
            }},
            {'$project': {'_id': 1, 'subject_doc.code': 1}}
        ])

        #query = {'project': {'$in': self.payload['sources']}}
        #source_subjects = config.db.subjects.find_many(
        #    query, user=None, projection={'_id': 1, 'code': 1})
        source_subject_ids = set()
        source_subject_codes = set()
        for source in source_subjects:
            source_subject_ids.add(source['_id'])
            source_subject_codes.add(source['subject_doc']['code'])

        # Conflicts are subjects that exist in the destination already
        conflicts = config.db.subjects.find_many({
            'code': {'$in': source_subject_codes},
            'project': self.dest_list[0]
        })

        # first we find conflicts as those are needed for dry run regardless.
        # Then we return that on dry run.
        final_conflicts = []
        conflict_subjects = []
        for conflict in conflicts:
            final_conflicts.append({'_id': conflict['_id'], 'code': conflict['code']})
            conflict_subjects.append(conflict['_id'])

        if self.payload.get('conflict_mode', True) or self.payload['conflict_mode'] is None or self.payload['conflict_mode'] == '':
            print 'we have these conflicts'
            print final_conflicts
            import sys
            sys.stdout.flush()
            return final_conflicts


        # Next we need to find the two sets that are not conflicts
            # copy: subjects that have more than one session in the source project
            # move: subjects that have just the one session in the source project
                # Techinically if all the sessions are in the move session

        # We just leave conflicts alone for now.
        search_subjects = source_subject_ids - set(conflict_subjects)

        sessions = config.db.sessions.aggregate([
            {'subject': {'$in': search_subjects}},
            {'$group': {'_id':'$subject', 'count': {'$sum':1}}},
            {'$match': {'count': {'$gt': 1}}},
            {'$project': {'subject': 1}}
        ])
        copy_subjects = []
        for session in sessions:
            copy_subjects.append(session['session'])

        sessions = config.db.sessions.aggregate([
            {'subject': {'$in': search_subjects}},
            {'$group': {'_id': '$subject', 'count': {'$sum': 1}}},
            {'$match': {'count': {'$eq': 1}}},
            {'$project': {'subject': 1}}
        ])
        move_subjects = []
        for session in sessions:
            move_subjects.append(session['session'])

        # Perhaps we can make this better with a single aggregation
        #sessions = config.db.sessions.aggregate([
        #    {'subject': {'$in': search_subjects}},
        #    { '$bucket': {
        #        'groupBy': ,
        #        'boundaries': [ 0, 200, 400 ],
        #          default: "Other",
        #          output: {
        #            "count": { $sum: 1 },
        #            "titles" : { $push: "$title" }
        #          }
        #        }
        #    }


        print 'we have these subjects to copy'
        print copy_subjects
        print 'we have these subjects to move'
        print move_subjects

        # quick sanity check
        assert len(source_subjects) == (
            len(move_subjects) + len(copy_subjects) + len(conflict_subjects))

        if self.payload['conflict_mode'] == 'move':
            sessions = config.db.sessions.find_many(
                {'subject': {'$in': conflict_subjects}},
                {'_id': 1})
        for session in sessions:
            move_subjects.append(session['_id'])

        print 'move sessions after conflict'
        print move_subjects



        # Move sesssions just need to have the pointers and permissions adjusted
        query = {'subject': {'$in': move_subjects}}
        update = {
            '$set': {
                'parents.project': project['_id'],
                'project': project['_id'],
                'permissions' : project['permissions']
            }
        }

        # Validate this method really works as expected
        containerutil.bulk_propagate_changes('session', move_subjects, query, update)

        # Copy sessions need to be copied including all related sub docs.
        # With mongo 4.1 we can do this in a pipeline.
        # Currently we have to pass the data back and update docs manually
        for subject in copy_subjects:
            # For each subject in copy subjects we need to copy the related analyses too.  Containers as well??
            # So we cant do a bulk copy like this
            #subjects = config.db.subjects.find_many({_'id': {'$in': copy_subjects}})
            #for subject in subjects:
            #    subject['_id'] = None
            #    subject['permissions'] = project['permissions']
            #    subject.project = project['_id']
            #    subject['parents']['project'] = project['_id']

            subject_doc = config.db.subjects.find_one({_'id': {'$in': copy_subjects}})
            subject_doc['_id'] = None
            subject_doc['permissions'] = project['permissions']
            subject_doc['project'] = project['_id']
            subject_doc['parents']['project'] = project['_id']
            new_subject = config.db.analyses.insert(subject_doc)
            
            analysis = config.db.analyses.find_many({'parent.type': 'subject', 'parent.id': subject})
            for analysis in analysis:
                analysis['_id'] = None
                analysis['permissions'] = project['permissions']
                analysis['parent']['id'] = subject
                analysis['parents']['subject'] = new_subject.last_inserted_id
                analysis['parents']['project'] = project['id']

                config.db.analysis.insert(analysis)
            


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
