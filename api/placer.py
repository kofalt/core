import bson
import copy
import datetime
import dateutil
import pymongo
import zipfile

import fs.path
import fs.errors

from . import config, util, validators
from .dao import containerutil, hierarchy
from .dao.containerstorage import SubjectStorage, SessionStorage, AcquisitionStorage
from .jobs import rules
from .jobs.jobs import Job, JobTicket, Logs
from .types import Origin
from .web import encoder
from .web.errors import FileFormException


CHUNK_SIZE = 1048576

class Placer(object):
    """
    Interface for a placer, which knows how to process files and place them where they belong - on disk and database.
    """

    def __init__(self, container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=config.log):
        self.container_type = container_type
        self.container      = container
        self.id_            = id_
        self.metadata       = metadata
        self.timestamp      = timestamp

        # An origin map for the caller
        self.origin         = origin

        # A placer-defined map for breaking the Placer abstraction layer.
        self.context        = context

        # Should the caller expect a normal map return, or a generator that gets mapped to Server-Sent Events?
        self.sse            = False

        # A list of files that have been saved via save_file() usually returned by finalize()
        self.saved          = []

        # A callable that allows the placer to log access information
        self.access_logger  = access_logger

        # A list of files that have been ignored by save_file() because a file with the same name and hash already existed
        self.ignored        = []

        # Context logger
        self.logger         = logger

        # Track failed rule evaluations
        self.failed_rules = []


    def check(self):
        """
        Run any pre-processing checks. Expected to throw on error.
        """
        raise NotImplementedError() # pragma: no cover

    def process_file_field(self, file_attrs):
        """"
        Process a single file field.
        """
        raise NotImplementedError() # pragma: no cover

    def finalize(self):
        """
        Run any post-processing work. Expected to return output for the callee.
        """
        raise NotImplementedError() # pragma: no cover

    def requireTarget(self):
        """
        Helper function that throws unless a container was provided.
        """
        if self.id_ is None or self.container is None or self.container_type is None:
            raise Exception('Must specify a target')

    def requireMetadata(self):
        """
        Helper function that throws unless metadata was provided.
        """
        if self.metadata == None:
            raise FileFormException('Metadata required')

    def save_file(self, file_attrs=None, ignore_hash_replace=False):
        """
        Helper function that moves a file saved via a form field into our CAS.
        May trigger jobs, if applicable, so this should only be called once we're ready for that.

        Requires an augmented file field; see process_upload() for details.
        """

        # Save file
        # We already have the file in the final location on persistent storage so we dont to do anything anymore

        # Update the DB
        if file_attrs is not None:

            container_before, self.container, saved_state = hierarchy.upsert_fileinfo(self.container_type, self.id_, file_attrs, self.access_logger,
                ignore_hash_replace=ignore_hash_replace, logger=self.logger)

            # If this file was ignored because an existing file with the same name and hash existed on this project,
            # add the file to the ignored list and move on
            if saved_state == 'ignored':
                self.ignored.append(file_attrs)

            else:
                self.saved.append(file_attrs)

                # create_jobs handles files that have been replaced differently
                replaced_files = []
                if saved_state == 'replaced':
                    replaced_files.append(containerutil.FileReference(self.container_type, self.id_, file_attrs['name']))

                rules.create_jobs(config.db, container_before, self.container, self.container_type, replaced_files=replaced_files,
                    rule_failure_callback=self.handle_rule_failure)

    def update_file(self, file_attrs):
        """
        If no file object is available, only the metadata will be updated
        """
        container_before, container_after, saved_state = hierarchy.update_fileinfo(self.container_type, self.id_, file_attrs)
        if saved_state == 'ignored':
            self.ignored.append(file_attrs)

        else:
            self.container = container_after
            rules.create_jobs(config.db, container_before, self.container, self.container_type,
                rule_failure_callback=self.handle_rule_failure)

    def recalc_session_compliance(self):
        if self.container_type in ['session', 'acquisition'] and self.id_:
            if self.container_type == 'session':
                session_id = self.id_
            else:
                session_id = AcquisitionStorage().get_container(str(self.id_)).get('session')
            SessionStorage().recalc_session_compliance(session_id, hard=True)

    def handle_rule_failure(self, rule, _exc_val):
        if rule not in self.failed_rules:
            self.failed_rules.append(rule)


class TargetedPlacer(Placer):
    """
    A placer that can accept 1 file to a specific container (acquisition, etc).
    """

    def check(self):
        self.requireTarget()
        validators.validate_data(self.metadata, 'file.json', 'input', 'POST', optional=True)

    def process_file_field(self, file_attrs):
        if self.metadata:
            file_attrs.update(self.metadata)
        self.save_file(file_attrs)


    def finalize(self):
        self.recalc_session_compliance()
        return self.saved


class TargetedMultiPlacer(TargetedPlacer):
    """
    A placer that can accept N files to a specific container (acquisition, etc).
    """

    def check(self):
        self.requireTarget()
        validators.validate_data(self.metadata, 'file-list.json', 'input', 'POST', optional=True)

    def process_file_field(self, file_attrs):
        if self.metadata:
            for fileinfo in self.metadata:
                if fileinfo['name'] == file_attrs['name']:
                    file_attrs.update(fileinfo)
        self.save_file(file_attrs)

class UIDPlacer(Placer):
    """
    A placer that can accept multiple files.
    It uses the method upsert_top_down_hierarchy to create its project/session/acquisition hierarchy
    Sessions and acquisitions are identified by UID.
    """
    metadata_schema = 'uidupload.json'
    create_hierarchy = staticmethod(hierarchy.upsert_top_down_hierarchy)
    match_type = 'uid'
    ignore_hash_replace = False


    def __init__(self, container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=config.log):
        super(UIDPlacer, self).__init__(container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=logger)
        self.metadata_for_file = {}
        self.session_id = None
        self.count = 0

    def check(self):
        self.requireMetadata()

        payload_schema_uri = validators.schema_uri('input', self.metadata_schema)
        metadata_validator = validators.from_schema_path(payload_schema_uri)
        metadata_validator(self.metadata, 'POST')



    def process_file_field(self, file_attrs):
        # Only create the hierarchy once
        if self.count == 0:
            # If not a superuser request, pass uid of user making the upload request
            targets = self.create_hierarchy(self.metadata, type_=self.match_type, user=self.context.get('uid'))

            self.metadata_for_file = {}

            for target in targets:
                if target[0].level is 'session':
                    self.session_id = target[0].id_
                for name in target[1]:
                    self.metadata_for_file[name] = {
                        'container': target[0],
                        'metadata': target[1][name]
                    }
        self.count += 1

        # For the file, given self.targets, choose a target
        name        = file_attrs['name']
        target      = self.metadata_for_file.get(name)

        # if the file was not included in the metadata skip it
        if not target:
            return
        container   = target['container']
        r_metadata  = target['metadata']
        file_attrs.update(r_metadata)

        self.container_type = container.level
        self.id_            = container.id_
        self.container      = container.container
        self.save_file(file_attrs, ignore_hash_replace=self.ignore_hash_replace)

    def finalize(self):
        # Check that there is at least one file being uploaded
        if self.count < 1:
            raise FileFormException("No files selected for upload")
        if self.session_id:
            self.container_type = 'session'
            self.id_ = self.session_id
            self.recalc_session_compliance()
        return self.saved


class UIDReaperPlacer(UIDPlacer):
    """
    A placer that creates or matches based on UID.

    Ignores project and group information if it finds session with matching UID.
    Allows users to move sessions during scans without causing new data to be
    created in referenced project/group.
    """

    metadata_schema = 'uidupload.json'
    create_hierarchy = staticmethod(hierarchy.upsert_bottom_up_hierarchy)
    match_type = 'uid'
    ignore_hash_replace = True


class LabelPlacer(UIDPlacer):
    """
    A placer that create a hierarchy based on labels.

    It uses the method upsert_top_down_hierarchy to create its project/session/acquisition hierarchy
    Sessions and acquisitions are identified by label.
    """

    metadata_schema = 'labelupload.json'
    create_hierarchy = staticmethod(hierarchy.upsert_top_down_hierarchy)
    match_type = 'label'
    ignore_hash_replace = False


class UIDMatchPlacer(UIDPlacer):
    """
    A placer that uploads to an existing hierarchy it finds based on uid.
    """

    metadata_schema = 'uidmatchupload.json'
    create_hierarchy = staticmethod(hierarchy.find_existing_hierarchy)
    match_type = 'uid'
    ignore_hash_replace = False



class EnginePlacer(Placer):
    """
    A placer that can accept files and/or metadata sent to it from the engine

    It uses update_container_hierarchy to update the container and its parents' fields from the metadata
    """

    def check(self):
        self.requireTarget()

        # Check that required state exists
        if self.context.get('job_id'):
            Job.get(self.context.get('job_id'))
        if self.context.get('job_ticket_id'):
            JobTicket.get(self.context.get('job_ticket_id'))

        if self.metadata is not None:
            validators.validate_data(self.metadata, 'enginemetadata.json', 'input', 'POST', optional=True)

            ###
            # Shuttle `measurements` key into `classification` on files
            ###

            if self.metadata.get(self.container_type, {}): # pragma: no cover

                for f in self.metadata[self.container_type].get('files', []):

                    if 'measurements' in f:
                        m = f.pop('measurements')
                        f['classification'] = {'Custom': m}
            ###

    def process_file_field(self, file_attrs):
        if self.metadata is not None:
            file_mds = self.metadata.get(self.container_type, {}).get('files', [])

            for file_md in file_mds:
                if file_md['name'] == file_attrs['name']:
                    file_attrs.update(file_md)
                    break

        self.save_file(file_attrs)

    def finalize(self):
        job = None

        if self.context.get('job_ticket_id'):
            job_ticket = JobTicket.get(self.context.get('job_ticket_id'))
            job = Job.get(job_ticket['job'])
        elif self.context.get('job_id'):
            job = Job.get(self.context.get('job_id'))

        # Save a deep-copy of produced metadata before
        # manipulation (if we're saving it to a job)
        produced_metadata = copy.deepcopy(self.metadata) if job is not None else None

        if self.metadata is not None:
            bid = bson.ObjectId(self.id_)

            file_mds = self.metadata.get(self.container_type, {}).get('files', [])
            saved_file_names = [x.get('name') for x in self.saved]
            for file_md in file_mds:

                # The job wants to update the metadata on this file
                if file_md['name'] not in saved_file_names:
                    self.update_file(file_md) # save file_attrs update only

            # Remove file metadata as it was already updated in process_file_field
            for k in self.metadata.keys():
                self.metadata[k].pop('files', {})

            hierarchy.update_container_hierarchy(self.metadata, bid, self.container_type)

        if job is not None:
            # Update profile info
            output_file_count = 0
            output_file_size_bytes = 0

            for f in self.saved:
                output_file_count += 1
                output_file_size_bytes += f['size']

            if job.profile is None:
                job.profile = {}

            job.profile['total_output_files'] =  output_file_count
            job.profile['total_output_size_bytes'] = output_file_size_bytes

            # Update saved files & metadata
            job.saved_files = [f['name'] for f in self.saved]
            job.produced_metadata = produced_metadata
            job.save()

        # Log any failed rules
        if self.failed_rules:
            lines = ['The following project rules could not be evaluated:\n']
            for rule in self.failed_rules:
                lines.append('  - {}: {}\n'.format(rule['_id'], rule.get('name')))
            Logs.add_system_logs(job.id_, lines)

        self.recalc_session_compliance()
        return self.saved


class TokenPlacer(Placer):
    """
    A placer that can accept N files and save them to a persistent directory across multiple requests.
    Intended for use with a token that tracks where the files will be stored.
    Is the strategy used between packfile-start and packfile-end
    """

    def __init__(self, container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=config.log):
        super(TokenPlacer, self).__init__(container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=logger)

        self.paths = []
        self.folder = None

    def check(self):
        token = self.context['token']

        if token is None:
            raise Exception('TokenPlacer requires a token')

        # This logic is used by:
        #   TokenPlacer.check
        #   PackfilePlacer.check
        #   upload.clean_packfile_tokens
        #
        # It must be kept in sync between each instance and also with the FileListHander tempdir.
        self.folder = fs.path.join('tokens', 'packfile', token)
        util.mkdir_p(self.folder, config.local_fs.get_fs())
        # we only work with local fs when using token placer

    def process_file_field(self, file_attrs):

        self.saved.append(file_attrs)
        self.paths.append(file_attrs['path'])

    def finalize(self):

        self.recalc_session_compliance()
        return self.saved


class PackfilePlacer(Placer):
    """
    A placer that can accept N files, save them into a zip archive, and place the result on an acquisition.
    """

    def __init__(self, container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=config.log):
        super(PackfilePlacer, self).__init__(container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=logger)

        self._chunk_size = CHUNK_SIZE

        # This endpoint is an SSE endpoint
        self.sse            = True

        # Populated in check(), used in finalize()
        self.p_id           = None
        self.s_label        = None
        self.s_code         = None
        self.a_label        = None
        self.a_time         = None
        self.g_id           = None

        self.permissions    = {}
        self.folder         = None
        self.dir_           = None
        self.name           = None
        self.path           = None
        self.zip_           = None
        self.ziptime        = None
        self.tempdir        = None


    def check(self):

        token = self.context['token']

        if token is None:
            raise Exception('PackfilePlacer requires a token')

        # This logic is used by:
        #   TokenPlacer.check
        #   PackfilePlacer.check
        #   upload.clean_packfile_tokens
        #
        # It must be kept in sync between each instance and also the FileListHandler tempdir.
        self.folder = fs.path.join('tokens', 'packfile', token)

        try:
            # Always on the local fs to make the pack file
            config.local_fs.get_fs().isdir(self.folder)
        except fs.errors.ResourceNotFound:
            raise Exception('Packfile directory does not exist or has been deleted')

        self.requireMetadata()
        validators.validate_data(self.metadata, 'packfile.json', 'input', 'POST')

        # Save required fields
        self.p_id  = self.metadata['project']['_id']
        self.s_label = self.metadata['session']['label']
        self.a_label = self.metadata['acquisition']['label']

        # Save additional fields if provided
        self.s_code = self.metadata['session'].get('subject', {}).get('code')
        self.a_time = self.metadata['acquisition'].get('timestamp')
        if self.a_time:
            self.a_time = dateutil.parser.parse(self.a_time)

        # Get project info that we need later
        project = config.db['projects'].find_one({ '_id': bson.ObjectId(self.p_id)})
        self.permissions = project.get('permissions', {})
        self.g_id = project['group']

        # If a timestamp was provided, use that for zip files. Otherwise use a set date.
        # Normally we'd use epoch, but zips cannot support years older than 1980, so let's use that instead.
        # Then, given the ISO string, convert it to an epoch integer.
        minimum = datetime.datetime(1980, 1, 1).isoformat()
        stamp   = self.metadata['acquisition'].get('timestamp', minimum)

        # If there was metadata sent back that predates the zip minimum, don't use it.
        #
        # Dateutil has overloaded the comparison operators, except it's totally useless:
        # > TypeError: can't compare offset-naive and offset-aware datetimes
        #
        # So instead, epoch-integer both and compare that way.
        if int(dateutil.parser.parse(stamp).strftime('%s')) < int(dateutil.parser.parse(minimum).strftime('%s')):
            stamp = minimum

        # Remember the timestamp integer for later use with os.utime.
        self.ziptime = dateutil.parser.parse(stamp)

        # The zipfile is a santizied acquisition label
        # But the dir is only ever used for human naming it seems
        self.dir_ = util.sanitize_string_to_filename(self.a_label)
        self.name = self.dir_ + '.zip'

        # OPPORTUNITY: add zip comment
        # self.zip.comment = json.dumps(metadata, default=metadata_encoder)


    def process_file_field(self, file_attrs):
        # Should not be called with any files but if it was then
        # remove the upload file that was saved direclty to storage from the form post
        config.local_fs.get_fs().remove(self.folder + '/' + file_attrs['name'])
        raise Exception('Files must already be uploaded')

    def finalize(self):
        paths = config.local_fs.get_fs().listdir(self.folder)
        total = len(paths)

        # We create the zip file in the local storage location then get attributes and then move it to the final
        # location. Otherwise in the cloud instances we would be writing files across the network which would
        # be much slower

        token = self.context['token']

        tempZipPath = fs.path.join('tokens', 'packfile', token, token)
        self.zip_ = zipfile.ZipFile(config.local_fs.get_fs().open(tempZipPath, 'wb'),
                                    'w', zipfile.ZIP_DEFLATED, allowZip64=True)
        # Write all files to zip
        complete = 0
        for path in paths:
            full_path = fs.path.join(self.folder, path)

            # Set the file's mtime & atime.
            config.local_fs.get_fs().settimes(full_path, self.ziptime, self.ziptime)

            # Place file into the zip folder we created before
            # Prepend the file paths with the label name by business logic decisions
            with config.local_fs.get_fs().open(full_path, 'rb') as f:
                self.zip_.writestr(self.dir_ + "/" + path, f.read())

            # Report progress
            complete += 1
            yield encoder.json_sse_pack({
                'event': 'progress',
                'data': { 'done': complete, 'total': total, 'percent': (complete / float(total)) * 100 },
            })

        self.zip_.close()

        # Lookup uid on token
        token  = self.context['token']
        uid = config.db['tokens'].find_one({ '_id': token }).get('user')
        self.origin = {
            'type': str(Origin.user),
            'id': uid
        }

        # Finaly move the file from the local fs to the persistent FS.
        # We could make this faster using a move if we know its a local to local fs move.
        with config.local_fs.get_fs().open(tempZipPath, 'rb') as (f1
                ), config.primary_storage.open(token, util.path_from_uuid(token), 'wb') as f2:
            while True:
                data = f1.read(self._chunk_size)
                if not data:
                    break
                f2.write(data)

        size = config.local_fs.get_file_info(token, tempZipPath)['filesize']
        hash_ = config.local_fs.get_file_hash(None, tempZipPath)

        # Remove the folder created by TokenPlacer after we calc the needed attributes
        config.local_fs.get_fs().removetree(self.folder)

        # Similarly, create the attributes map that is consumed by helper funcs. Clear duplication :(
        # This could be coalesced into a single map thrown on file fields, for example.
        # Used in the API return.
        cgi_attrs = {
            '_id': token,
            'name': self.name,
            'modified': self.timestamp,
            'path' : util.path_from_uuid(token),
            'size': size,
            'zip_member_count': complete,
            'hash': hash_,
            'mimetype': util.guess_mimetype('lol.zip'),
            'type': self.metadata['packfile']['type'],

            # OPPORTUNITY: packfile endpoint could be extended someday to take additional metadata.
            'modality': None,
            'classification': {},
            'tags': [],
            'info': {},

            # Manually add the file orign to the packfile metadata.
            # This is set by upload.process_upload on each file, but we're not storing those.
            'origin': self.origin
        }

        # Get or create a session based on the hierarchy and provided labels.
        query = {
            'project': bson.ObjectId(self.p_id),
            'label': self.s_label,
            'group': self.g_id,
            'deleted': {'$exists': False}
        }

        # Updates if existing
        updates = util.mongo_dict({
            'permissions': self.permissions,
            'modified': self.timestamp,
        })

        # Properties on insert
        insert_map = {
            'project': bson.ObjectId(self.p_id),
            'label': self.s_label,
            'group': self.g_id,
            'created': self.timestamp,
        }
        insert_map.update(self.metadata['session'])
        if 'timestamp' in insert_map:
            insert_map['timestamp'] = dateutil.parser.parse(insert_map['timestamp'])

        session_exists = config.db.sessions.find_one(query)
        if self.s_code or not session_exists:
            project = {'_id': bson.ObjectId(self.p_id), 'permissions': self.permissions}
            subject = containerutil.extract_subject(insert_map, project)
            SubjectStorage().create_or_update_el(subject)
            query['subject'] = subject['_id']

            insert_map['parents'] = {
                'group': self.g_id,
                'project': bson.ObjectId(self.p_id),
                'subject': subject['_id']
            }

        session = config.db.sessions.find_one_and_update(
            query, {
                '$set': updates,
                '$setOnInsert': insert_map
            },
            upsert=True,
            return_document=pymongo.collection.ReturnDocument.AFTER
        )

        # Get or create an acquisition based on the hierarchy and provided labels.
        query = {
            'session': session['_id'],
            'label': self.a_label,
            'deleted': {'$exists': False}
        }

        if self.a_time:
            # If they supplied an acquisition timestamp, use that in the query as well
            query['timestamp'] = self.a_time


        # Updates if existing
        updates = {}
        updates['permissions'] = self.permissions
        updates['modified']    = self.timestamp
        updates = util.mongo_dict(updates)

        # Extra properties on insert
        insert_map = copy.deepcopy(query)
        insert_map['parents'] = copy.deepcopy(session['parents'])
        insert_map['parents']['session'] = session['_id']

        # Remove query term that should not become part of the payload
        insert_map.pop('deleted')

        insert_map['created'] = self.timestamp
        insert_map.update(self.metadata['acquisition'])
        if 'timestamp' in insert_map:
            insert_map['timestamp'] = dateutil.parser.parse(insert_map['timestamp'])

        acquisition = config.db.acquisitions.find_one_and_update(
            query, {
                '$set': updates,
                '$setOnInsert': insert_map
            },
            upsert=True,
            return_document=pymongo.collection.ReturnDocument.AFTER
        )

        # Set instance target for helper func
        self.container_type = 'acquisition'
        self.id_            = str(acquisition['_id'])
        self.container	    = acquisition

        self.save_file(cgi_attrs)

        # Set target for session recalc
        self.container_type = 'session'
        self.id_            = str(session['_id'])
        self.container      = session

        self.recalc_session_compliance()

        # Delete token
        config.db['tokens'].delete_one({ '_id': token })

        result = {
            'acquisition_id': str(acquisition['_id']),
            'session_id':	 str(session['_id']),
            'info': cgi_attrs
        }

        # Report result
        yield encoder.json_sse_pack({
            'event': 'result',
            'data': result,
        })


class AnalysisPlacer(Placer):
    def check(self):
        self.requireMetadata()
        validators.validate_data(self.metadata, 'analysis-legacy.json', 'input', 'POST', optional=True)

    def process_file_field(self, file_attrs):
        self.save_file()
        self.saved.append(file_attrs)

    def finalize(self):
        # Merge fileinfos from the processed upload into the metadata from the payload (for inputs and outputs)
        upload_fileinfos = {fileinfo['name']: fileinfo for fileinfo in self.saved}
        if 'outputs' in self.metadata:
            self.metadata['files'] = self.metadata.pop('outputs')
        for filegroup in ('inputs', 'files'):
            for meta_fileinfo in self.metadata.get(filegroup, []):
                # TODO warn (err?) on meta for unknown filename?
                meta_fileinfo.update(upload_fileinfos.get(meta_fileinfo['name'], {}))
        return self.metadata


class AnalysisJobPlacer(Placer):
    def check(self):
        self.requireTarget()

        # Check that required state exists
        if self.context.get('job_id'):
            Job.get(self.context.get('job_id'))
        if self.context.get('job_ticket_id'):
            JobTicket.get(self.context.get('job_ticket_id'))

    def process_file_field(self, file_attrs):
        if self.metadata is not None:
            file_mds = self.metadata.get('acquisition', {}).get('files', [])

            for file_md in file_mds:
                if file_md['name'] == file_attrs['name']:
                    file_attrs.update(file_md)
                    break

        file_attrs['created'] = file_attrs['modified']
        self.save_file(None)
        self.saved.append(file_attrs)

    def finalize(self):
        job = None

        if self.context.get('job_ticket_id'):
            job_ticket = JobTicket.get(self.context.get('job_ticket_id'))
            job = Job.get(job_ticket['job'])
        elif self.context.get('job_id'):
            job = Job.get(self.context.get('job_id'))

        # Replace analysis files (and job in case it's re-run)
        query = {'_id': self.id_}
        update = {'$set': {'files': self.saved}}
        if job is not None:
            update['$set']['job'] = job.id_
        config.db.analyses.update_one(query, update)

        if job is not None:
            # Update profile info
            output_file_count = 0
            output_file_size_bytes = 0

            for f in self.saved:
                output_file_count += 1
                output_file_size_bytes += f['size']

            if job.profile is None:
                job.profile = {}

            job.profile['total_output_files'] =  output_file_count
            job.profile['total_output_size_bytes'] = output_file_size_bytes

            #Update saved files
            job.saved_files = [f['name'] for f in self.saved]
            job.save()

        return self.saved


class GearPlacer(Placer):
    def check(self):
        self.requireMetadata()

    def process_file_field(self, file_attrs):
        if self.metadata:
            file_attrs.update(self.metadata)
            proper_hash = file_attrs.get('hash')[3:].replace('-', ':')
            self.metadata.update({'exchange': {'rootfs-hash': proper_hash,
                                               'git-commit': 'local',
                                               'rootfs-url': 'INVALID',
                                               'rootfs-id': file_attrs['_id']}})
        # self.metadata['hash'] = file_attrs.get('hash')

        self.save_file()
        self.saved.append(file_attrs)
        self.saved.append(self.metadata)

    def finalize(self):
        return self.saved
