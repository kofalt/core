
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

        source_session = self.source_storage.get_el(self.source_list[0])
        dest_project = self.dest_storage.get_el(self.dest_list[0])

        # hash of projects by id for quick lookup


        # Find all the source subjects first.
        source_subjects = config.db.sessions.aggregate([
            {'$match': {'_id': {'$in': self.source_list}}},
            {'$group': {'_id': '$subject'}},
            {'$lookup':{
                'from': 'subjects',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'subject_doc'
            }},
            {'$project': {'_id': 1, 'subject_doc.code': 1, 'subject_doc.project': 1}}
        ])

        source_subject_ids = []
        source_subject_codes = []
        source_projects = []
        source_subject_id_by_code = {} # We need the mapping of source id by code for conflicts later
        for source in source_subjects:
            source_subject_ids.append(source['_id'])
            source_projects.append(source['subject_doc'][0]['project'])
            # not all subejcts have a code.  If not they will not be a conflict anyway
            if source['subject_doc'][0].get('code'):
                source_subject_codes.append(source['subject_doc'][0]['code'])
                source_subject_id_by_code[source['subject_doc'][0]['code']] = source['_id']

        print 'we have these subjects to move'
        print source_subject_ids
        print source_subject_codes
        print '----------------------------'


        # Conflict codes are subject codes that exist in the destination already
        conflicts = config.db.subjects.find({
            'code': {'$in': source_subject_codes},
            'project': self.dest_list[0]
            }, projection={'_id': 1, 'code': 1})

        # first we find conflicts as those are needed for dry run regardless.
        conflict_subject_codes = []
        conflict_subject_dest_ids_by_code = {}
        for conflict in conflicts:
            conflict_subject_codes.append(conflict['code'])
            conflict_subject_dest_ids_by_code[conflict['code']] = conflict['_id']

        if (not self.payload.get('conflict_mode', False) or
                self.payload['conflict_mode'] is None or self.payload['conflict_mode'] == ''):
            # TODO: Raise an error
            return conflict_subject_codes

        # The id of the subjects in the source that have the same code
        conflict_subject_source_ids = []
        #conflict_subject_source_ids_by_code = {} # might be needed for conflict resolution later
        conflicts = config.db.subjects.find(
                {'code': {'$in': conflict_subject_codes}, 'project': {'$in': list(set(source_projects))}},
            projection={'_id': 1, 'code': 1})
        for conflict in conflicts:
            conflict_subject_source_ids.append(conflict['_id'])
            #conflict_subject_source_ids_by_code[conflict['code']] = conflict['_id']


        print 'we have confilcts'
        print conflict_subject_source_ids
        import sys
        sys.stdout.flush()

        # We need source projects for all the sessions to update

        # Next we need to find the two sets that are not conflicts
            # copy: subjects that have more than one session in the source project
            # move: subjects that have just the one session in the source project
                # Techinically if all the sessions are in the move session

        # We just leave conflicts alone for now.
        search_subjects = list(set(source_subject_ids) - set(conflict_subject_source_ids))
        print 'we have these subjects to search on'
        print search_subjects

        sessions = config.db.sessions.aggregate([
            {'$match': {'subject': {'$in': search_subjects}}},
            {'$group': {'_id': '$subject', 'count': {'$sum':1}}},
            {'$match': {'count': {'$gt': 1}}},
            {'$project': {'_id': 1}}
        ])
        copy_subjects = []
        for session in sessions:
            copy_subjects.append(session['_id'])

        sessions = config.db.sessions.aggregate([
            {'$match': {'subject': {'$in': search_subjects}}},
            {'$group': {'_id': '$subject', 'count': {'$sum': 1}}},
            {'$match': {'count': {'$eq': 1}}},
            {'$project': {'_id': 1}}
        ])
        move_subjects = []
        for session in sessions:
            move_subjects.append(session['_id'])

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
        print 'we have these conflict subjects'
        print conflict_subject_source_ids
        print 'Innintal total size of subjects'
        print source_subject_ids
        import sys
        sys.stdout.flush()

        # quick sanity check
        assert len(source_subject_ids) == (
            len(move_subjects) + len(copy_subjects) + len(conflict_subject_source_ids))

        if self.payload['conflict_mode'] == 'move':
            # We have to move the sessions which means updating the session to have the new subject id and parent, project, permissions
            # But we need to find the ID of the subject in the dest project first.
            for code in conflict_subject_codes:
                print 'processing a conflict code'
                print code
                query = {
                    'parents.subject': source_subject_id_by_code[code],
                    '_id': {'$in': self.source_list}
                }
                update = {'$set': {
                    'subject': conflict_subject_dest_ids_by_code[code],
                    'parents.subject': conflict_subject_dest_ids_by_code[code],
                    'parents.project': self.dest_list[0],
                    'project': self.dest_list[0],
                    'permissions': dest_project['permissions']
                }}

                moves = []
                sessions = config.db.sessions.find({
                    'subject': source_subject_id_by_code[code],
                    '_id': {'$in': self.source_list}}, projection= {'_id': 1})
                for session in sessions:
                    moves.append(session['_id'])

                print 'we are propogating a move for these conflict sessions'
                print moves
                import sys
                sys.stdout.flush()

                containerutil.bulk_propagate_changes('sessions', moves, query, update, include_refs=True)


        # Move subjects just need to have the pointers and permissions adjusted
        #query = {'_id': {'$in': move_subjects}, '_id': {'$in': self.source_list}}
        query = {}
        update = {
            '$set': {
                'parents.project': self.dest_list[0],
                'project': self.dest_list[0],
                'permissions': dest_project['permissions']
            }
        }

        # Validate this method really works as expected
        print 'We are propogating a move for these subjects'
        print move_subjects
        containerutil.bulk_propagate_changes('subjects', move_subjects, query, update, include_refs=True)

        # Copy sessions need to be copied including all related sub docs.
        # With mongo 4.1 we can do this in a pipeline.
        # Currently we have to pass the data back and update docs manually
        for subject in copy_subjects:
            subject_doc = config.db.subjects.find_one({'_id': {'$in': copy_subjects}})
            del subject_doc['_id']
            subject_doc['permissions'] = dest_project['permissions']
            subject_doc['project'] = dest_project['_id']
            subject_doc['parents']['project'] = dest_project['_id']
            new_subject = config.db.subject.insert_one(subject_doc)
            print 'we have a new subject'
            print new_subject

            analysis = config.db.analyses.find({'parent.type': 'subject', 'parent.id': subject})
            for a in analysis:
                print 'we are updating an analysis'
                print analysis
                import sys
                sys.stdout.flush()
                a['_id'] = None
                a['permissions'] = dest_project['permissions']
                a['parent']['id'] = new_subject.inserted_id
                a['parents']['subject'] = new_subject.inserted_id
                a['parents']['project'] = dest_project['id']

                config.db.analysis.insert_one(analysis)

            # Find the sessions for this subject that need to be moved now
            sessions = config.db.sessions.find({
                'subject': subject, '_id': {'$in': self.source_list}}, projection={'_id': 1})
            moves = []
            for session in sessions:
                moves.append(session['_id'])


            # Now the sessions can be moved to the new subject with propagation
            #query = {'subject': subject, '_id': {'$in': self.source_list}}
            query = {}
            update = {'$set': {
                'permissions': dest_project['permissions'],
                'project': dest_project['_id'],
                'parents.project': dest_project['_id'],
                'parents.subject': new_subject.inserted_id,
                'subject': new_subject.inserted_id,
                }}
            print 'We are propogating a move for these sessions now that we have a copied subject'
            print moves
            import sys
            sys.stdout.flush()
            containerutil.bulk_propagate_changes('sessions', moves, query, update, include_refs=True)

            # Techinically any subjects in the source that no longer have sessions should be deleted
            # Otherwise we have dangling subjects

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
