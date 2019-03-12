"""
Jobs
"""

import bson
import copy
import datetime
import string
from urlparse import urlparse

from ..types import Origin
from ..dao.containerutil import create_filereference_from_dictionary, create_containerreference_from_dictionary

from .. import config
from ..web.errors import APINotFoundException

class Job(object):
    def __init__(self, gear, inputs, destination=None, tags=None,
                 attempt=1, previous_job_id=None, created=None,
                 modified=None, retried=None, state='pending',
                 request=None, id_=None, config_=None, origin=None,
                 saved_files=None, produced_metadata=None, batch=None,
                 failed_output_accepted=False, profile=None,
                 parents=None, failure_reason=None, transitions=None,
                 related_container_ids=None, label=None, compute_provider_id=None):
        """
        Creates a job.

        Parameters
        ----------
        gear: map
            The gear doc (includes unique _id)
        inputs: string -> FileReference map
            The inputs to be used by this job
        destination: ContainerReference (optional)
            Where to place the gear's output. Defaults to one of the input's containers.
        tags: string array (optional)
            Tags that this job should be marked with.
        attempt: integer (optional)
            If an equivalent job has tried & failed before, pass which attempt number we're at. Defaults to 1 (no previous attempts).
        previous_job_id: string (optional)
            If an equivalent job has tried & failed before, pass the last job attempt. Defaults to None (no previous attempts).
        created: datetime (optional)
        modified: datetime (optional)
            Timestamps
        state: string (optional)
            The state of this job. Defaults to 'pending'.
        request: map (optional)
            The request that is used for the engine. Generated when job is started.
        id_: string (optional)
            The database identifier for this job.
        config: map (optional)
            The gear configuration for this job.
        failed_output_accepted: bool (optional)
            Flag indicating whether output was accepted for a failed job.
        profile: map (optional)
            The optional detailed job statistics object
        parents: map (optional)
            The optional parents, as a copy of destination parents at time of creation
        failure_reason:  string (optional)
            If the job was marked as failed, the reason for the failure
        transitions: dict (optional)
            The set of timestamps associated with state changes
        related_container_ids: list (optional)
            The set of all container ids related to inputs and destination of this job, as of
            job creation time. This field is not updated when containers are moved.
        label: str (optional)
            An optional label for the job
        compute_provider_id: ObjectId (optional)
            The compute provider id for job execution
        """

        # TODO: validate inputs against the manifest

        gear_id = str(gear['_id'])

        time_now = datetime.datetime.utcnow()

        if tags is None:
            tags = []
        if saved_files is None:
            saved_files = []
        if produced_metadata is None:
            produced_metadata = {}
        if created is None:
            created = time_now
        if modified is None:
            modified = time_now
        if profile is None:
            profile = {}


        # Trim tags array to unique members...
        tags = list(set(tags))

        # If no origin, mark as system origin
        if origin is None:
            origin = {
                'type': str(Origin.system),
                'id': None
            }

        # Partial join of gear info at time of execution
        gear_info = {
            'category': gear.get('category'),
            'name': gear['gear']['name'],
            'version': gear['gear']['version'],
            'capabilities': gear['gear'].get('capabilities', [])
        }

        self.gear_id            = gear_id
        self.gear_info          = gear_info
        self.inputs             = inputs
        self.destination        = destination
        self.tags               = tags
        self.attempt            = attempt
        self.previous_job_id    = previous_job_id
        self.created            = created
        self.modified           = modified
        self.retried            = retried
        self.state              = state
        self.request            = request
        self.id_                = id_
        self.config             = config_
        self.origin             = origin
        self.saved_files        = saved_files
        self.produced_metadata  = produced_metadata
        self.batch              = batch
        self.failed_output_accepted = failed_output_accepted
        self.profile            = profile
        self.parents            = parents
        self.failure_reason     = failure_reason
        self.transitions        = transitions
        self.related_container_ids = related_container_ids
        self.label              = label
        self.compute_provider_id = compute_provider_id

    def intention_equals(self, other_job):
        """
        Compare this job's intention to other_job.
        Returns True if other_job's gear_id, inputs and destination match self.
        Returns False otherwise.

        Useful for comparing auto-triggered jobs for equality.
        Implicitly uses dict, FileReference and ContainerReference _cmp_ methods.
        """
        if (
            isinstance(other_job, Job) and
            self.gear_id == other_job.gear_id and
            self.inputs == other_job.inputs and
            self.destination == other_job.destination
        ):
            return True

        else:
            return False

    @classmethod
    def load(cls, e):
        # TODO: validate

        # Don't modify the map
        d = copy.deepcopy(e)

        if d.get('inputs'):
            input_dict = {}

            for i in d['inputs']:
                inp = i.pop('input')
                if 'type' in i and 'name' in i:
                    input_dict[inp] = create_filereference_from_dictionary(i)
                else:
                    input_dict[inp] = i

            d['inputs'] = input_dict

        if d.get('destination', None):
            d['destination'] = create_containerreference_from_dictionary(d['destination'])

        d['_id'] = str(d['_id'])

        gear_info = d.get('gear_info', {})
        gear_doc = {
            '_id': d['gear_id'],
            'category': gear_info.get('category'),
            'gear': {
                'name': gear_info.get('name'),
                'version': gear_info.get('version'),
                'capabilities': gear_info.get('capabilities', []),
            }
        }

        return cls(gear_doc, d.get('inputs'),
            destination=d.get('destination'),
            tags=d['tags'], attempt=d['attempt'],
            previous_job_id=d.get('previous_job_id'),
            created=d['created'],
            modified=d['modified'],
            retried=d.get('retried'),
            state=d['state'],
            request=d.get('request'),
            id_=d['_id'],
            config_=d.get('config'),
            origin=d.get('origin'),
            saved_files=d.get('saved_files'),
            produced_metadata=d.get('produced_metadata'),
            batch=d.get('batch'),
            failed_output_accepted=d.get('failed_output_accepted', False),
            profile=d.get('profile', {}),
            parents = d.get('parents', {}),
            failure_reason=d.get('failure_reason'),
            transitions=d.get('transitions', {}),
            related_container_ids=d.get('related_container_ids', []),
            label = d.get('label'),
            compute_provider_id = d.get('compute_provider_id')
        )

    @classmethod
    def get(cls, _id):
        doc = config.db.jobs.find_one({'_id': bson.ObjectId(_id)})
        if doc is None:
            raise APINotFoundException('Job not found')

        return cls.load(doc)

    def map(self):
        """
        Flatten struct to map
        """

        # Don't modify the job obj
        d = copy.deepcopy(self.__dict__)

        d['id'] = d.pop('id_', None)

        if d.get('inputs'):
            for x in d['inputs'].keys():
                if not isinstance(d['inputs'][x], dict):
                    d['inputs'][x] = d['inputs'][x].__dict__
        else:
            d.pop('inputs')

        if d.get('destination'):
            d['destination'] = d['destination'].__dict__
        else:
            d.pop('destination')

        if d['id'] is None:
            d.pop('id')
        if d['previous_job_id'] is None:
            d.pop('previous_job_id')
        if d['request'] is None:
            d.pop('request')
        if d['failed_output_accepted'] is False:
            d.pop('failed_output_accepted')
        if d['retried'] is None:
            d.pop('retried')
        if d.get('parents') is None:
            d.pop('parents')
        if d['failure_reason'] is None:
            d.pop('failure_reason')
        if d.get('transitions') is None:
            d.pop('transitions')
        if d.get('related_container_ids') is None:
            d.pop('related_container_ids')

        return d

    def mongo(self):
        d = self.map()
        if d.get('id'):
            d['_id'] = bson.ObjectId(d.pop('id'))
        if d.get('inputs'):
            input_array = []
            for k, inp in d['inputs'].iteritems():
                inp['input'] = k
                input_array.append(inp)
            d['inputs'] = input_array

        return d

    def insert(self, ignore_insertion_block=False):
        """
        Warning: this will not stop you from inserting a job for a gear that has gear.custom.flywheel.invalid set to true.
        """

        if self.id_ is not None and not ignore_insertion_block:
            raise Exception('Cannot insert job that has already been inserted')

        result = config.db.jobs.insert_one(self.mongo())
        self.id_ = result.inserted_id
        return result.inserted_id

    def save(self):
        self.modified = datetime.datetime.utcnow()
        update = self.mongo()
        job_id = update.pop('_id')
        result = config.db.jobs.replace_one({'_id': job_id}, update)
        if result.modified_count != 1:
            raise Exception('Job modification not saved')
        return {'modified_count': 1}

    def generate_request(self, gear):
        """
        Generate the job's request, save it to the class, and return it

        Parameters
        ----------
        gear: map
            A gear_list map from the gears table.
        """

        if gear['gear'].get('custom', {}).get('flywheel', {}).get('invalid', False):
            raise Exception('Gear marked as invalid, will not run!')

        uri = gear['exchange']['rootfs-url']
        parsed = urlparse(uri)
        scheme = parsed.scheme

        if scheme == 'https' or scheme == '':
            # SSL does not change the input scheme type, both are just 'http'
            scheme = 'http'
        else:
            # Other URI types keep the input scheme separate
            uri = parsed.netloc + parsed.path

        r = {
            'inputs': [
                {
                    'type': scheme,
                    'uri': uri,
                    'location': '/',
                }
            ],
            'target': {
                'command': None,
                'env': {
                    'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
                },
                'dir': '/flywheel/v0',
            },
            'outputs': [
                {
                    'type': 'scitran',
                    'uri': '',
                    'location': '/flywheel/v0/output',
                },
            ],
        }

        custom_uid = gear['gear'].get('custom', {}).get('flywheel', {}).get('uid', 0)
        custom_gid = gear['gear'].get('custom', {}).get('flywheel', {}).get('gid', 0)

        if custom_uid > 0 or custom_gid > 0:
            r['target']['uid'] = int(custom_uid)
            r['target']['gid'] = int(custom_gid)

        # Map destination to upload URI
        r['outputs'][0]['uri'] = '/engine?level=' + self.destination.type + '&id=' + self.destination.id

        # Add environment, if any
        for key in gear['gear'].get('environment', {}).keys():
            r['target']['env'][key] = gear['gear']['environment'][key]

        # Add command, if any
        command_base = ''
        if gear['gear'].get('command') is not None:
            r['target']['command'] = ['bash', '-c', command_base + gear['gear']['command'] ]
        else:
            r['target']['command'] = ['bash', '-c', command_base + './run' ]

        # Add config, if any
        if self.config is not None:

            if self.id_ is None:
                raise Exception('Running a job requires an ID')

            # Detect if config is old- or new-style.
            # TODO: remove this logic with a DB upgrade, ref database.py's reserved upgrade section.

            # Add config scalars as environment variables
            if self.config.get('config') is not None and self.config.get('inputs') is not None:
                # New config behavior

                cf = self.config['config']

                # Whitelist characters that can be used in bash variable names
                bash_variable_letters = set(string.ascii_letters + string.digits + ' ' + '_')

                for x in cf:
                    # Strip non-whitelisted characters, set to underscore, and uppercase
                    config_name = filter(lambda char: char in bash_variable_letters, x)
                    config_name = config_name.replace(' ', '_').upper()

                    # Don't set nonsensical environment variables
                    if config_name == '':
                        print 'The gear config name ' + x + ' has no whitelisted characters!'
                        continue

                    if isinstance(cf[x], list):
                        # Stringify array or set
                        # Might have same issue as scalars with "True" >:(
                        r['target']['env']['FW_CONFIG_' + config_name] = str(cf[x])

                    elif isinstance(cf[x], dict):
                        raise Exception('Disallowed object-type config value ' + x + ' ' + str(cf[x]))

                    else:
                        # Stringify scalar
                        # Python strings true as "True"; fix
                        if not isinstance(cf[x], bool):
                            r['target']['env']['FW_CONFIG_' + config_name] = str(cf[x])
                        else:
                            r['target']['env']['FW_CONFIG_' + config_name] = str(cf[x]).lower()

            else:
                # Old config map.
                pass

            r['inputs'].append({
                'type': 'scitran',
                'uri': '/jobs/' + self.id_ + '/config.json',
                'location': '/flywheel/v0',
            })

        # Add the files
        if self.inputs is not None:
            for input_name in self.inputs.keys():
                i = self.inputs[input_name]

                if hasattr(i, 'file_uri'):
                    r['inputs'].append({
                        'type': 'scitran',
                        'uri': i.file_uri(i.name),
                        'location': '/flywheel/v0/input/' + input_name,
                    })

        # Log job origin if provided
        if self.id_:
            r['outputs'][0]['uri'] += '&job=' + self.id_

        self.request = r
        return self.request

class JobTicket(object):
    """
    A JobTicket represents an attempt to complete a job.
    """

    @staticmethod
    def get(_id):
        return config.db.job_tickets.find_one({'_id': bson.ObjectId(_id)})

    @staticmethod
    def create(job_id):
        j = Job.get(job_id)

        result = config.db.job_tickets.insert_one({
            'job': j.id_,
            'timestamp': datetime.datetime.utcnow(),
        })

        return result.inserted_id

    @staticmethod
    def find(job_id):
        """Find any tickets with job ID"""
        return list(config.db.job_tickets.find({'job': str(job_id)}))

    @staticmethod
    def remove(_id):
        """Remove a single ticket by id"""
        config.db.job_tickets.remove({'_id': bson.ObjectId(_id)})

class Logs(object):

    @staticmethod
    def get(_id):
        log = config.db.job_logs.find_one({'_id': _id})

        if log is None:
            return { '_id': _id, 'logs': [] }
        else:
            return log

    @staticmethod
    def get_text_generator(_id):
        log = config.db.job_logs.find_one({'_id': _id})

        if log is None:
            yield '<span class="fd--1">No logs were found for this job.</span>'
        else:
            for stanza in log['logs']:
                msg = stanza['msg']
                yield msg

    @staticmethod
    def get_html_generator(_id):
        log = config.db.job_logs.find_one({'_id': _id})

        if log is None:
            yield '<span class="fd--1">No logs were found for this job.</span>'

        else:
            open_span = False
            last = None

            for stanza in log['logs']:
                fd = stanza['fd']
                msg = stanza['msg']

                if fd != last:
                    if open_span:
                        yield '</span>\n'

                    yield '<span class="fd-' + str(fd) + '">'
                    open_span = True
                    last = fd

                yield msg.replace('\n', '<br/>\n')

            if open_span:
                yield '</span>\n'

    @staticmethod
    def add(_id, doc):

        # Silently ignore adding no logs
        if len(doc) <= 0:
            return

        log = config.db.job_logs.find_one({'_id': _id})

        if log is None: # Race
            config.db.job_logs.insert_one({'_id': _id, 'logs': []})

        config.db.job_logs.update({'_id': _id}, {'$push':{'logs':{'$each':doc}}})

    @staticmethod
    def add_system_logs(_id, lines):
        """Shortcut method for adding system logs to a job"""
        if not lines:
            return

        if isinstance(lines, str):
            lines = [lines]

        Logs.add(_id, [{'msg': line, 'fd': -1} for line in lines])
