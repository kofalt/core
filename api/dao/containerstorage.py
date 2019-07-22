import datetime
import bson
import copy

from . import containerutil
from . import hierarchy
from .. import config
from .. import util

from ..util import deep_update
from ..jobs.jobs import Job
from ..jobs.queue import Queue
from ..jobs.rules import copy_site_rules_for_project
from ..web.errors import APIStorageException, APINotFoundException, APIValidationException
from .basecontainerstorage import ContainerStorage

log = config.log


# Python circular reference workaround
# Can be removed when dao module is reworked
def cs_factory(cont_name):
    return ContainerStorage.factory(cont_name)


class GroupStorage(ContainerStorage):

    def __init__(self):
        super(GroupStorage, self).__init__('groups', use_object_id=False, parent_cont_name=None, child_cont_name='project')

    def _to_mongo(self, payload):
        # Ascertain defaults in our model for consistency
        payload.setdefault('editions', {}).setdefault('lab', False)

    def _fill_default_values(self, cont):
        cont = super(GroupStorage,self)._fill_default_values(cont)
        if cont:
            if 'permissions' not in cont:
                cont['permissions'] = []
            if 'editions' not in cont:
                cont['editions'] = {'lab': False}
        return cont

    def create_el(self, payload, origin):
        permissions = payload.pop('permissions')
        created = payload.pop('created')
        self._to_mongo(payload)

        # Groups do not need ad-hoc check and do not call Super
        return self.dbc.update_one(
            {'_id': payload['_id']},
            {
                '$set': payload,
                '$setOnInsert': {'permissions': permissions, 'created': created}
            },
            upsert=True)

    def cleanup_ancillary_data(self, _id):
        safe_cleanup_views(_id)

    def revert_lab_edition(self, _id):
        """Revert all children projects to have lab edition off"""
        config.db.projects.update_many({'parents.group': _id}, {'$set': {'editions.lab': False}})

class UserStorage(ContainerStorage):

    def __init__(self):
        super(UserStorage,self).__init__('users', use_object_id=False)

    def cleanup_ancillary_data(self, _id):
        safe_cleanup_views(_id)
        self.cleanup_user_permissions(_id)

    def cleanup_user_permissions(self, uid):
        """Remove user from the permissions array of every container"""
        try:
            query = {'permissions._id': uid}
            update = {'$pull': {'permissions' : {'_id': uid}}}

            for cont in ['collections', 'groups', 'projects', 'sessions', 'acquisitions']:
                config.db[cont].update_many(query, update)

        except APIStorageException:
            raise APIStorageException('Site-wide user permissions for {} were unabled to be removed'.format(uid))

    def _from_mongo(self, cont):
        # Remove password_hash, if it exists
        if cont is not None:
            cont.pop('password_hash', None)


class ProjectStorage(ContainerStorage):
    def __init__(self):
        super(ProjectStorage,self).__init__('projects', use_object_id=True, use_delete_tag=True, parent_cont_name='group', child_cont_name='subject')

    def _to_mongo(self, payload):
        if not payload.get('editions'):
            # Ascertain defaults in our model for consistency
            payload['editions'] = {'lab': False}
            return

        if not 'lab' in payload['editions']:
            payload['editions']['lab'] = False

    def create_el(self, payload, origin):

        result = super(ProjectStorage, self).create_el(payload, origin)
        copy_site_rules_for_project(result.inserted_id)
        return result

    def update_el(self, _id, payload, unset_payload=None, recursive=False, r_payload=None, replace_metadata=False):

        result = super(ProjectStorage, self).update_el(_id, payload, unset_payload=unset_payload, recursive=recursive, r_payload=r_payload, replace_metadata=replace_metadata)

        if result.modified_count < 1:
            raise APINotFoundException('Could not find project {}'.format(_id))

        if payload and 'templates' in payload:
            # We are adding/changing the project template, update session compliance
            sessions = self.get_children(_id, projection={'_id':1}, include_subjects=False)
            session_storage = SessionStorage()
            for s in sessions:
                session_storage.update_el(s['_id'], {'project_has_template': True})

        elif unset_payload and 'templates' in unset_payload:
            # We are removing the project template, remove session compliance
            sessions = self.get_children(_id, projection={'_id':1}, include_subjects=False)
            session_storage = SessionStorage()
            for s in sessions:
                session_storage.update_el(s['_id'], None, unset_payload={'project_has_template': '', 'satisfies_template': ''})

        return result

    def recalc_sessions_compliance(self, project_id=None):
        if project_id is None:
            # Recalc all projects
            projects = self.get_all_el({'templates': {'$exists': True}}, None, None)
        else:
            project = self.get_container(project_id)
            if project:
                projects = [project]
            else:
                raise APINotFoundException('Could not find project {}'.format(project_id))
        changed_sessions = []

        for project in projects:
            templates = project.get('templates',[])
            if not templates:
                continue
            else:
                session_storage = SessionStorage()
                sessions = session_storage.get_all_el({'project': project['_id']}, None, None)
                for s in sessions:
                    changed = session_storage.recalc_session_compliance(s['_id'], session=s, templates=templates, hard=True)
                    if changed:
                        changed_sessions.append(s['_id'])
        return changed_sessions

    def get_list_projection(self):
        return {'info': 0, 'files.info': 0}

    def cleanup_ancillary_data(self, _id):
        safe_cleanup_views(_id)


class SubjectStorage(ContainerStorage):

    def __init__(self):
        super(SubjectStorage, self).__init__('subjects', use_object_id=True, use_delete_tag=True, parent_cont_name='project', child_cont_name='session')

    def _from_mongo(self, cont):
        if cont is not None:
            if cont.get('code'):
                cont['label'] = cont['code']
            else:
                cont['label'] = 'unknown'

    def create_or_update_el(self, payload, origin, **kwargs):
        if self.dbc.find_one({'_id': payload['_id'], 'deleted': {'$exists': False}}):
            payload['modified'] = datetime.datetime.utcnow()
            # Pop _id from mongo payload (immutable - would raise error)
            payload_copy = copy.deepcopy(payload)
            _id = payload_copy.pop('_id')
            return super(SubjectStorage, self).update_el(_id, payload_copy, **kwargs)
        elif self.dbc.find_one({'_id': payload['_id']}):
            # If the subject exists but is deleted, create a new subject with a new id
            # This logic should only be used by the placers/hierarchy.py
            # Other subject operations should be going through
            # extract_subject which prevents this from happening
            payload.pop('_id')

        payload['created'] = payload['modified'] = datetime.datetime.utcnow()
        return super(SubjectStorage, self).create_el(payload, origin)

    def get_all_el(self, query, user, projection, fill_defaults=False, pagination=None, **kwargs):
        """Allow 'collections' query key"""
        if query and query.get('collections'):
            # Add filter to query to only match subjects that have sessions with acquisitions in this collection
            collection_id = query.pop('collections')
            # TODO limit subject join / fix projection on session storage
            sessions = SessionStorage().get_all_el({'collections': bson.ObjectId(collection_id)}, None, {'subject': 1}, **kwargs)
            query['_id'] = {'$in': list(set([sess['subject']['_id'] for sess in sessions]))}

        return super(SubjectStorage, self).get_all_el(query, user, projection, fill_defaults=fill_defaults, pagination=pagination, **kwargs)

    def get_list_projection(self):
        return {'info': 0, 'files.info': 0, 'firstname': 0, 'lastname': 0, 'sex': 0, 'race': 0, 'ethnicity': 0}


class SessionStorage(ContainerStorage):

    def __init__(self):
        super(SessionStorage,self).__init__('sessions', use_object_id=True, use_delete_tag=True, parent_cont_name='subject', child_cont_name='acquisition')

    def _fill_default_values(self, cont):
        cont = super(SessionStorage, self)._fill_default_values(cont)
        if cont:
            s_defaults = {'analyses': [], 'subject': {}}
            s_defaults.update(cont)
            cont = s_defaults
        return cont

    def create_el(self, payload, origin):

        project = ProjectStorage().get_container(payload['project'])
        if project.get('template'):
            payload['project_has_template'] = True
            payload['satisfies_template'] = hierarchy.is_session_compliant(payload, project.get('template'))
        return super(SessionStorage, self).create_el(payload, origin)

    def update_el(self, _id, payload, unset_payload=None, recursive=False, r_payload=None, replace_metadata=False):
        session = self.get_container(_id)
        if session is None:
            raise APINotFoundException('Could not find session {}'.format(_id))

        # Determine if we need to calc session compliance
        # First check if project is being changed
        if payload and payload.get('project'):
            project = ProjectStorage().get_container(payload['project'])
            if not project:
                raise APINotFoundException("Could not find project {}".format(payload['project']))
        else:
            project = ProjectStorage().get_container(session['project'])

        # Check if new (if project is changed) or current project has template
        payload_has_template = project.get('templates', False)
        session_has_template = session.get('project_has_template') is not None
        unset_payload_has_template = (unset_payload and 'project_has_template'in unset_payload)

        if payload_has_template or (session_has_template and not unset_payload_has_template):
            session_update = copy.deepcopy(payload)
            if 'subject' in payload:
                session_update['subject'] = config.db.subjects.find_one({'_id': payload['subject']})
            session = deep_update(session, session_update)
            if project and project.get('templates'):
                payload['project_has_template'] = True
                payload['satisfies_template'] = hierarchy.is_session_compliant(session, project.get('templates'))
            elif project:
                if not unset_payload:
                    unset_payload = {}
                unset_payload['satisfies_template'] = ""
                unset_payload['project_has_template'] = ""
        return super(SessionStorage, self).update_el(_id, payload, unset_payload=unset_payload, recursive=recursive, r_payload=r_payload, replace_metadata=replace_metadata)

    def get_all_el(self, query, user, projection, fill_defaults=False, pagination=None, **kwargs):
        """Allow 'collections' query key"""
        if query and query.get('collections'):
            # Add filter to query to only match sessions that have acquisitions in this collection
            collection_id = query.pop('collections')
            acquisitions = AcquisitionStorage().get_all_el({'collections': bson.ObjectId(collection_id)}, None, {'session': 1}, **kwargs)
            query['_id'] = {'$in': list(set([a['session'] for a in acquisitions]))}

        return super(SessionStorage, self).get_all_el(query, user, projection, fill_defaults=fill_defaults, pagination=pagination, **kwargs)


    def recalc_session_compliance(self, session_id, session=None, templates=None, hard=False):
        """
        Calculates a session's compliance with the project's session template.
        Returns True if the status changed, False otherwise
        """
        if session is None:
            session = self.get_container(session_id)
        if session is None:
            raise APINotFoundException('Could not find session {}'.format(session_id))
        if hard:
            # A "hard" flag will also recalc if session is tracked by a project template

            project = ProjectStorage().get_container(session['project'])
            project_has_template = bool(project.get('templates'))
            if session.get('project_has_template', False) != project_has_template:
                if project_has_template == True:
                    self.update_el(session['_id'], {'project_has_template': True})
                else:
                    self.update_el(session['_id'], None, unset_payload={'project_has_template': '', 'satisfies_template': ''})
                return True
        if session.get('project_has_template'):
            if templates is None:
                templates = ProjectStorage().get_container(session['project']).get('templates')
            satisfies_template = hierarchy.is_session_compliant(session, templates)
            if session.get('satisfies_template') != satisfies_template:
                update = {'satisfies_template': satisfies_template}
                super(SessionStorage, self).update_el(session_id, update)
                return True
        return False

    def get_all_for_targets(self, target_type, target_ids, user=None, projection=None):
        """
        Given a container type and list of ids, get all sessions that are in those hierarchies.

        For example, if target_type='projects' and target_ids=['id1', 'id2'], this method will return
        all sessions that are in project id1 and project id2.

        Params `target_ids` and `collection`

        If user is supplied, will only return sessions with user in its perms list.
        If projection is supplied, it will be applied to the session query.
        """

        query = {}
        target_type = containerutil.singularize(target_type)

        if target_type == 'project':
            query['project'] = {'$in':target_ids}

        elif target_type == 'session':
            query['_id'] = {'$in':target_ids}

        elif target_type == 'acquisition':
            a_query = copy.deepcopy(query)
            a_query['_id'] = {'$in':target_ids}
            session_ids = list(set([a['session'] for a in AcquisitionStorage().get_all_el(a_query, user, {'session':1})]))
            query['_id'] = {'$in':session_ids}

        else:
            raise ValueError('Cannot get all sessions from target container {}'.format(target_type))

        return self.get_all_el(query, user, projection)

    def get_list_projection(self):
        return {'info': 0, 'files.info': 0, 'analyses': 0, 'tags': 0, 'age': 0}

    # Keeps the same signature even if mode is not required
    # pylint: disable=unused-argument
    def move_sessions_to_subject(self, source_list, dest_subject, conflict_mode=None):

        dest_subject_obj = SubjectStorage().get_el(dest_subject)

        query = {}
        update = {'$set': {
            'parents.subject': dest_subject_obj['_id'],
            'parents.project': dest_subject_obj['parents']['project'],
            'parents.group': dest_subject_obj['parents']['group'],
            'subject': dest_subject_obj['_id'],
            'project': dest_subject_obj['parents']['project'],
            'group': dest_subject_obj['parents']['group'],
            'permissions': dest_subject_obj['permissions']
        }}

        # Sessions can not have conflicts so just bilndly move them all over to the new subject.
        containerutil.bulk_propagate_changes('sessions', source_list, query,
             update, include_refs=True)


    def move_sessions_to_project(self, source_list, dest_project, conflict_mode=None):

        dest_project_obj = ProjectStorage().get_el(dest_project)

        # Find all the source subjects first.
        source_subjects = config.db.sessions.aggregate([
            {'$match': {'_id': {'$in': source_list}}},
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
            # We can have missing subjects. Not sure this is a valid case
            if not source['subject_doc']:
                continue
            source_projects.append(source['subject_doc'][0]['project'])
            # not all subjects have a code.  If not they will not be a conflict anyway
            if source['subject_doc'][0].get('code'):
                source_subject_codes.append(source['subject_doc'][0]['code'])
                source_subject_id_by_code[source['subject_doc'][0]['code']] = source['_id']


        # Conflict codes are subject codes that exist in the destination already
        conflicts = config.db.subjects.find({
            'code': {'$in': source_subject_codes},
            'project': dest_project_obj['_id']
            }, projection={'_id': 1, 'code': 1})

        # first we find conflicts as those are needed for dry run regardless.
        conflict_subject_codes = []
        conflict_subject_dest_ids_by_code = {}
        for conflict in conflicts:
            conflict_subject_codes.append(conflict['code'])
            conflict_subject_dest_ids_by_code[conflict['code']] = conflict['_id']

        # Without explicit conflict mode we assume a dry run
        if not conflict_mode:
            return conflict_subject_codes

        # The id of the subjects in the source that have the same code
        conflict_subject_source_ids = []
        conflicts = config.db.subjects.find(
            {
                'code': {'$in': conflict_subject_codes},
                'project': {'$in': list(set(source_projects))}
            },
            projection={'_id': 1, 'code': 1})

        for conflict in conflicts:
            conflict_subject_source_ids.append(conflict['_id'])


        # We need source projects for all the sessions to update
        # We just leave conflicts alone for now.
        search_subjects = list(set(source_subject_ids) - set(conflict_subject_source_ids))

        # IF the sessions are a subset its move if not its copy
        # Regardless of how many sessions the subject has
        copy_subjects = []
        move_subjects = []
        source_list_set = set(source_list)
        sessions = config.db.sessions.aggregate([
            {'$match': {'subject': {'$in': search_subjects}}},
            {'$group': {'_id': '$subject', 'count': {'$sum':1}, 'sessions': {'$push': "$_id"}}},
            #{'$match': {'count': {'$gt': 1}}},
            {'$project': {'_id': 1, 'sessions': 1, 'count': 1}}
        ])
        for session in sessions:
            # If the set size is 1 then we can save the set conversion and math
            if session['count'] == 1:
                move_subjects.append(session['_id'])
                continue
            # If we are moving all the sessions then we dont need to copy the subject.
            if set(session['sessions']).issubset(source_list_set):
                move_subjects.append(session['_id'])
                continue
            copy_subjects.append(session['_id'])

        # quick sanity check
        assert len(source_subject_ids) == (
            len(move_subjects) + len(copy_subjects) + len(conflict_subject_source_ids))

        if conflict_mode == 'move':
            # We have to move the sessions which means updating the session to have the new
            # subject id,  parent, project, and permissions
            # But we need to find the ID of the subject in the dest project first.
            for code in conflict_subject_codes:
                query = {
                    'parents.subject': source_subject_id_by_code[code],
                    '_id': {'$in': source_list}
                }
                update = {'$set': {
                    'subject': conflict_subject_dest_ids_by_code[code],
                    'parents.subject': conflict_subject_dest_ids_by_code[code],
                    'parents.project': dest_project_obj['_id'],
                    'project': dest_project_obj['_id'],
                    'permissions': dest_project_obj['permissions']
                }}

                moves = []
                sessions = config.db.sessions.find({
                    'subject': source_subject_id_by_code[code],
                    '_id': {'$in': source_list}}, projection={'_id': 1})
                for session in sessions:
                    moves.append(session['_id'])

                containerutil.bulk_propagate_changes('sessions', moves, query,
                    update, include_refs=True)


        # Move subjects just need to have the pointers and permissions adjusted
        query = {}
        update = {
            '$set': {
                'parents.project': dest_project_obj['_id'],
                'parents.group': dest_project_obj['parents']['group'],
                'project': dest_project_obj['_id'],
                'permissions': dest_project_obj['permissions']
            }
        }

        containerutil.bulk_propagate_changes('subjects', move_subjects, query,
             update, include_refs=True)

        # Copy sessions need to be copied including all related sub docs.
        # With mongo 4.1 we can do this in a pipeline.
        # Currently we have to pass the data back and update docs manually
        for subject in copy_subjects:
            subject_doc = config.db.subjects.find_one({'_id': bson.ObjectId(subject)})
            del subject_doc['_id']
            subject_doc['permissions'] = dest_project_obj['permissions']
            subject_doc['project'] = dest_project_obj['_id']
            subject_doc['parents']['group'] = dest_project_obj['parents']['group']
            subject_doc['parents']['project'] = dest_project_obj['_id']
            # These we need to do one at a time because we need the inserted id.
            # We could tweak this by creating a placeholder and then updating the unique
            # placeholder once the final subjects are flushed and have vaild objectIds
            new_subject = config.db.subjects.insert_one(subject_doc)

            analysis = config.db.analyses.find({'parent.type': 'subject', 'parent.id': subject})
            # We might have a memory issue depending on the size of  anayses we have to move
            # At the max doc size of 16 mb this could be 800MB.
            insert_analyses = []
            count = 0
            page = 50
            for a in analysis:
                a['_id'] = None
                a['permissions'] = dest_project_obj['permissions']
                a['parent']['id'] = new_subject.inserted_id
                a['parents']['subject'] = new_subject.inserted_id
                a['parents']['project'] = dest_project_obj['id']
                a['parents']['group'] = dest_project_obj['parents']['group']
                if count <= page:
                    insert_analyses.append(a)
                else:
                    config.db.analysis.insert_many(insert_analyses)
                    insert_analyses = []
                    count = 0
            if insert_analyses:
                config.db.analysis.insert_many(insert_analyses)

            # Find the sessions for this subject that need to be moved now
            sessions = config.db.sessions.find({
                'subject': subject, '_id': {'$in': source_list}}, projection={'_id': 1})
            moves = []
            for session in sessions:
                moves.append(session['_id'])

            # Now the sessions can be moved to the new subject with propagation
            query = {}
            update = {'$set': {
                'permissions': dest_project_obj['permissions'],
                'project': dest_project_obj['_id'],
                'parents.group': dest_project_obj['parents']['group'],
                'parents.project': dest_project_obj['_id'],
                'parents.subject': new_subject.inserted_id,
                'subject': new_subject.inserted_id,
                }}
            containerutil.bulk_propagate_changes('sessions', moves, query, update, include_refs=True)


    def move_sessions_to_project(self, source_list, dest_project, conflict_mode=None):

        dest_project_obj = ProjectStorage().get_el(dest_project)

        # Find all the source subjects first.
        source_subjects = config.db.sessions.aggregate([
            {'$match': {'_id': {'$in': source_list}}},
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


        # Conflict codes are subject codes that exist in the destination already
        conflicts = config.db.subjects.find({
            'code': {'$in': source_subject_codes},
            'project': dest_project_obj['_id']
            }, projection={'_id': 1, 'code': 1})

        # first we find conflicts as those are needed for dry run regardless.
        conflict_subject_codes = []
        conflict_subject_dest_ids_by_code = {}
        for conflict in conflicts:
            conflict_subject_codes.append(conflict['code'])
            conflict_subject_dest_ids_by_code[conflict['code']] = conflict['_id']

        # Without explicit conflict mode we assume a dry run
        if not conflict_mode:
            return conflict_subject_codes

        # The id of the subjects in the source that have the same code
        conflict_subject_source_ids = []
        #conflict_subject_source_ids_by_code = {} # might be needed for conflict resolution later
        conflicts = config.db.subjects.find(
            {
                'code': {'$in': conflict_subject_codes},
                'project': {'$in': list(set(source_projects))}
            },
            projection={'_id': 1, 'code': 1})

        for conflict in conflicts:
            conflict_subject_source_ids.append(conflict['_id'])
            #conflict_subject_source_ids_by_code[conflict['code']] = conflict['_id']


        # We need source projects for all the sessions to update

        # Next we need to find the two sets that are not conflicts
            # copy: subjects that have more than one session in the source project
            # move: subjects that have just the one session in the source project
                # TODO:
                # Techinically if all the sessions are in the source list then its a move

        # We just leave conflicts alone for now.
        search_subjects = list(set(source_subject_ids) - set(conflict_subject_source_ids))

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


        # quick sanity check
        assert len(source_subject_ids) == (
            len(move_subjects) + len(copy_subjects) + len(conflict_subject_source_ids))

        if conflict_mode == 'move':
            # We have to move the sessions which means updating the session to have the new
            # subject id,  parent, project, and permissions
            # But we need to find the ID of the subject in the dest project first.
            for code in conflict_subject_codes:
                query = {
                    'parents.subject': source_subject_id_by_code[code],
                    '_id': {'$in': source_list}
                }
                update = {'$set': {
                    'subject': conflict_subject_dest_ids_by_code[code],
                    'parents.subject': conflict_subject_dest_ids_by_code[code],
                    'parents.project': dest_project_obj['_id'],
                    'project': dest_project_obj['_id'],
                    'permissions': dest_project_obj['permissions']
                }}

                moves = []
                sessions = config.db.sessions.find({
                    'subject': source_subject_id_by_code[code],
                    '_id': {'$in': source_list}}, projection={'_id': 1})
                for session in sessions:
                    moves.append(session['_id'])

                containerutil.bulk_propagate_changes('sessions', moves, query, 
                    update, include_refs=True)


        # Move subjects just need to have the pointers and permissions adjusted
        query = {}
        update = {
            '$set': {
                'parents.project': dest_project_obj['_id'],
                'project': dest_project_obj['_id'],
                'permissions': dest_project_obj['permissions']
            }
        }

        # TODO: Validate this method really works as expected
        containerutil.bulk_propagate_changes('subjects', move_subjects, query,
             update, include_refs=True)

        # Copy sessions need to be copied including all related sub docs.
        # With mongo 4.1 we can do this in a pipeline.
        # Currently we have to pass the data back and update docs manually
        for subject in copy_subjects:
            subject_doc = config.db.subjects.find_one({'_id': {'$in': copy_subjects}})
            del subject_doc['_id']
            subject_doc['permissions'] = dest_project_obj['permissions']
            subject_doc['project'] = dest_project_obj['_id']
            subject_doc['parents']['project'] = dest_project_obj['_id']
            new_subject = config.db.subject.insert_one(subject_doc)

            analysis = config.db.analyses.find({'parent.type': 'subject', 'parent.id': subject})
            for a in analysis:
                a['_id'] = None
                a['permissions'] = dest_project_obj['permissions']
                a['parent']['id'] = new_subject.inserted_id
                a['parents']['subject'] = new_subject.inserted_id
                a['parents']['project'] = dest_project_obj['id']

                config.db.analysis.insert_one(analysis)

            # Find the sessions for this subject that need to be moved now
            sessions = config.db.sessions.find({
                'subject': subject, '_id': {'$in': source_list}}, projection={'_id': 1})
            moves = []
            for session in sessions:
                moves.append(session['_id'])


            # Now the sessions can be moved to the new subject with propagation
            #query = {'subject': subject, '_id': {'$in': self.source_list}}
            query = {}
            update = {'$set': {
                'permissions': dest_project_obj['permissions'],
                'project': dest_project_obj['_id'],
                'parents.project': dest_project_obj['_id'],
                'parents.subject': new_subject.inserted_id,
                'subject': new_subject.inserted_id,
                }}
            containerutil.bulk_propagate_changes('sessions', moves, query, update, include_refs=True)


class AcquisitionStorage(ContainerStorage):

    def __init__(self):
        super(AcquisitionStorage,self).__init__('acquisitions', use_object_id=True, use_delete_tag=True, parent_cont_name='session', child_cont_name=None)

    def create_el(self, payload, origin):
        result = super(AcquisitionStorage, self).create_el(payload, origin)
        SessionStorage().recalc_session_compliance(payload['session'])
        return result

    def update_el(self, _id, payload, unset_payload=None, recursive=False, r_payload=None, replace_metadata=False):
        result = super(AcquisitionStorage, self).update_el(_id, payload, unset_payload=unset_payload, recursive=recursive, r_payload=r_payload, replace_metadata=replace_metadata)
        acquisition = self.get_container(_id)
        if acquisition is None:
            raise APINotFoundException('Could not find acquisition {}'.format(_id))
        SessionStorage().recalc_session_compliance(acquisition['session'])
        return result

    def delete_el(self, _id):
        acquisition = self.get_container(_id)
        if acquisition is None:
            raise APINotFoundException('Could not find acquisition {}'.format(_id))
        result = super(AcquisitionStorage, self).delete_el(_id)
        SessionStorage().recalc_session_compliance(acquisition['session'])
        return result

    def get_all_for_targets(self, target_type, target_ids, user=None, projection=None, collection_id=None):
        """
        Given a container type and list of ids, get all acquisitions that are in those hierarchies.

        For example, if target_type='projects' and target_ids=['id1', 'id2'], this method will return
        all acquisitions that are in sessions in project id1 and project id2.

        Params `target_ids` and `collection`

        If user is supplied, will only return acquisitions with user in its perms list.
        If projection is supplied, it will be applied to the acquisition query.
        If colllection is supplied, the collection context will be used to query acquisitions.
        """

        query = {}

        # If target_type is 'acquisitions', it just wraps self.get_all_el with a query containing
        # all acquisition ids.
        if target_type in ['acquisition', 'acquisitions']:
            query['_id'] = {'$in':target_ids}
            return self.get_all_el(query, user, projection)

        # Find session ids from projects
        session_ids = None
        if target_type in ['project', 'projects']:
            query['project'] = {'$in':target_ids}
            session_ids = [s['_id'] for s in SessionStorage().get_all_el(query, user, {'_id':1})]
        elif target_type in ['session', 'sessions']:
            session_ids = target_ids
        else:
            raise ValueError('Target type must be of type project, session or acquisition.')

        # Using session ids, find acquisitions
        query.pop('project', None)
        query['session'] = {'$in':session_ids}
        if collection_id:
            query['collections'] = collection_id
        return self.get_all_el(query, user, projection)

    def get_list_projection(self):
        return {'info': 0, 'collections': 0, 'files.info': 0, 'tags': 0}


class CollectionStorage(ContainerStorage):

    def __init__(self):
        super(CollectionStorage, self).__init__('collections', use_object_id=True, use_delete_tag=True)

    def get_list_projection(self):
        return {'info': 0, 'files.info': 0}


class AnalysisStorage(ContainerStorage):

    def __init__(self):
        super(AnalysisStorage, self).__init__('analyses', use_object_id=True, use_delete_tag=True)


    def get_parent(self, _id, cont=None, projection=None):
        if not cont:
            cont = self.get_container(_id, projection=projection)

        ps = ContainerStorage.factory(cont['parent']['type'])
        return ps.get_container(cont['parent']['id'], projection=projection)

    def get_parent_tree(self, _id, cont=None, projection=None, add_self=False):
        if not cont:
            cont = self.get_container(_id, projection=projection)

        ps = ContainerStorage.factory(cont['parent']['type'])

        return ps.get_parent_tree(cont['parent']['id'], add_self=True)


    def get_analyses(self, query, parent_type, parent_id, inflate_job_info=False, projection=None, **kwargs):
        if query is None:
            query = {}
        query['parent.type'] = containerutil.singularize(parent_type)
        query['parent.id'] = bson.ObjectId(parent_id)

        analyses = self.get_all_el(query, None, projection, **kwargs)
        if inflate_job_info:
            for analysis in analyses:
                self.inflate_job_info(analysis, remove_phi=True)
        return analyses


    # pylint: disable=arguments-differ
    def create_el(self, analysis, parent_type, parent_id, origin, uid=None):
        """
        Create an analysis.
        * Fill defaults if not provided
        * Flatten input filerefs using `FileReference.get_file()`
        If `analysis` has a `job` key, create a "job-based" analysis:
            * Analysis inputs will be copied from the job inputs
            * Create analysis and job, both referencing each other
            * Do not create (remove) analysis if can't enqueue job
        """
        parent_type = containerutil.singularize(parent_type)
        parent = self.get_parent(None, cont={'parent': {'type': parent_type, 'id': parent_id}})
        defaults = {
            '_id': bson.ObjectId(),
            'parent': {
                'type': parent_type,
                'id': bson.ObjectId(parent_id)
            },
            'created': datetime.datetime.utcnow(),
            'modified': datetime.datetime.utcnow(),
            'user': origin.get('id')
        }

        for key in defaults:
            analysis.setdefault(key, defaults[key])
        if 'public' in parent:
            analysis.setdefault('public', parent['public'])

        job = analysis.pop('job', None)
        if job is not None:
            if parent_type not in ['project', 'session', 'subject', 'acquisition']:
                raise APIValidationException(reason='Cannot create analysis via job at the {} level'.format(parent_type))
            analysis.setdefault('inputs', [])
            for key, fileref_dict in job['inputs'].iteritems():
                analysis['inputs'].append(fileref_dict)

        # Verify and flatten input filerefs
        for i, fileref_dict in enumerate(analysis.get('inputs', [])):
            try:
                fileref = containerutil.create_filereference_from_dictionary(fileref_dict)
            except KeyError:
                # Legacy analyses already have fileinfos as inputs instead of filerefs
                pass
            else:
                analysis['inputs'][i] = fileref.get_file()

        if analysis.get('info') is not None:
            analysis['info'] = util.mongo_sanitize_fields(analysis['info'])

        result = super(AnalysisStorage, self).create_el(analysis, origin)
        if not result.acknowledged:
            raise APIStorageException('Analysis not created for container {} {}'.format(parent_type, parent_id))

        if job is not None:
            # Create job
            job['destination'] = {'type': 'analysis', 'id': str(analysis['_id'])}
            tags = job.get('tags', [])
            if 'analysis' not in tags:
                tags.append('analysis')
                job['tags'] = tags

            try:
                job = Queue.enqueue_job(job, origin, perm_check_uid=uid)
                job.insert()

                # Copy gear info and add id
                gear_info = job.gear_info.copy()
                gear_info['id'] = job.gear_id

                self.update_el(analysis['_id'], {
                    'job': job.id_,
                    'gear_info': gear_info
                }, None)
            except:
                # NOTE #775 remove unusable analysis - until jobs have a 'hold' state
                self.delete_el(analysis['_id'])
                raise

        return result


    def inflate_job_info(self, analysis, remove_phi=False):
        """
        Inflate job from id ref in analysis

        Lookup job via id stored on analysis
        Lookup input filerefs and inflate into files array with 'input': True
        If job is in failed state, look for most recent job referencing this analysis
        Update analysis if new job is found
        """

        if analysis.get('job') is None:
            return analysis
        try:
            job = Job.get(analysis['job'])
        except:
            raise Exception('No job with id {} found.'.format(analysis['job']))

        if remove_phi:
            job = job.remove_potential_phi_from_job()

        analysis['job'] = job
        return analysis

    def get_list_projection(self):
        return {'info': 0, 'files.info': 0, 'tags': 0}


class QueryStorage(ContainerStorage):

    def __init__(self):
        super(QueryStorage, self).__init__('queries', use_object_id=True)

    def get_parent(self, _id, cont=None, projection=None):
        """Returns parent

        Args:
            _id (str): The id of the query
            cont (dict): The optional query itself if already retrieved
            projection (dict): Projection to apply to parent

        Returns:
            str: The literal string 'site'
            dict: The parent container
        """
        if not cont:
            cont = self.get_container(_id)
        parent_reference = cont['parent']

        parent_id = parent_reference['id']
        if parent_reference['type'] == 'site':
            return 'site'
        elif parent_reference['type'] == 'project':
            parent_id = bson.ObjectId(parent_id)

        ps = ContainerStorage.factory(containerutil.pluralize(parent_reference['type']))
        return ps.get_container(parent_id, projection=projection)

    def _get_user_parents(self, uid, user_is_admin=False):
        """Get a list of query parent types that user has access

        Args:
            uid (str): The id of the user to get parent ids for
            user_is_admin (bool): User is or isn't site admin

        Returns:
            list: list of ids of parents as strings
        """
        # Everyone has access to read queries on the site and on themselves
        parents = [uid]
        if user_is_admin:
            parents.append('site')

        # Get the projects they have access (ids as strings)
        parents += [str(p['_id']) for p in ProjectStorage().get_all_el(None, {'_id': uid}, {'_id': 1})]

        # Get the groups that user has access to
        parents += [g['_id'] for g in GroupStorage().get_all_el(None, {'_id': uid}, {'_id': 1})]

        return parents

    def get_all_el(self, query, user, projection, fill_defaults=False, pagination=None, **kwargs):
        """Return all queries

        Args:
            query (dict|None): The query to give
            user (dict|None): The user if filetering for access to the query
            projection (dict|None): The query to apply to results
            fill_defaults (bool): Whether or not to populate the default values for returned elements. Default is False.
            pagination (dict): The pagination options. Default is None.
            **kwargs: Additional arguments to pass to the underlying find function

        Returns:
            list: Queries
        """
        if user is not None:
            query = query or {}
            query.update({
                'parent.id': {
                    '$in': self._get_user_parents(user['_id'],
                                                  user.get('root', False))
                }
            })
        return super(QueryStorage, self).get_all_el(query, None, projection,
                                                    fill_defaults=fill_defaults,
                                                    pagination=pagination, **kwargs)


def safe_cleanup_views(parent_id):
    """ Delete all data views belonging to the parent container, trapping any exceptions.

    Arguments:
        parent_id (str,ObjectId): The parent container id
    """
    try:
        config.db.data_views.remove({'parent': str(parent_id)})
    except APIStorageException as e:
        log.warn('Unable to cleanup views for container {} - {}'.format(parent_id, e))
