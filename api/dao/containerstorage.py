import datetime
import bson
import copy

from . import containerutil
from . import hierarchy
from .. import config

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
        super(GroupStorage,self).__init__('groups', use_object_id=False, parent_cont_name=None, child_cont_name='project')

    def _fill_default_values(self, cont):
        cont = super(GroupStorage,self)._fill_default_values(cont)
        if cont:
            if 'permissions' not in cont:
                cont['permissions'] = []
        return cont

    def create_el(self, payload):
        permissions = payload.pop('permissions')
        created = payload.pop('created')
        return self.dbc.update_one(
            {'_id': payload['_id']},
            {
                '$set': payload,
                '$setOnInsert': {'permissions': permissions, 'created': created}
            },
            upsert=True)

    def cleanup_ancillary_data(self, _id):
        safe_cleanup_views(_id)

class UserStorage(ContainerStorage):

    def __init__(self):
        super(UserStorage,self).__init__('users', use_object_id=True)

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


class ProjectStorage(ContainerStorage):
    def __init__(self):
        super(ProjectStorage,self).__init__('projects', use_object_id=True, use_delete_tag=True, parent_cont_name='group', child_cont_name='subject')

    def create_el(self, payload):
        result = super(ProjectStorage, self).create_el(payload)
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

    def create_or_update_el(self, payload, **kwargs):
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
        return super(SubjectStorage, self).create_el(payload)

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

    def create_el(self, payload):
        project = ProjectStorage().get_container(payload['project'])
        if project.get('template'):
            payload['project_has_template'] = True
            payload['satisfies_template'] = hierarchy.is_session_compliant(payload, project.get('template'))
        return super(SessionStorage, self).create_el(payload)

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


class AcquisitionStorage(ContainerStorage):

    def __init__(self):
        super(AcquisitionStorage,self).__init__('acquisitions', use_object_id=True, use_delete_tag=True, parent_cont_name='session', child_cont_name=None)

    def create_el(self, payload):
        result = super(AcquisitionStorage, self).create_el(payload)
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
                self.inflate_job_info(analysis)
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


        result = super(AnalysisStorage, self).create_el(analysis)
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


    def inflate_job_info(self, analysis):
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

        analysis['job'] = job
        return analysis

    def get_list_projection(self):
        return {'info': 0, 'files.info': 0, 'tags': 0}

class QueryStorage(ContainerStorage):

    def __init__(self):
        super(QueryStorage, self).__init__('queries', use_object_id=True)

def safe_cleanup_views(parent_id):
    """ Delete all data views belonging to the parent container, trapping any exceptions.

    Arguments:
        parent_id (str,ObjectId): The parent container id
    """
    try:
        config.db.data_views.remove({'parent': str(parent_id)})
    except APIStorageException as e:
        log.warn('Unable to cleanup views for container {} - {}'.format(parent_id, e))
