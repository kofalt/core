import bson

from . import basedownload

from ..web import base
from ..web.errors import APIPermissionException, APINotFoundException
from .. import config, validators
from ..auth import require_login

BYTES_IN_MEGABYTE = float(1<<20)


class DownloadHandler(base.RequestHandler):

    @require_login
    def download(self):
        """Download files or create a download ticket"""

        uid = None
        if not self.user_is_admin:
            uid = self.uid

        downloader = basedownload.BaseDownload(
            download_type = 'default',
            access_logger = self.log_user_access,
            logger = self.log,
            prefix = self.get_param('prefix', 'flywheel'),
            request = self.request,
            uid = uid,
            origin = self.origin)

        ticket_id = self.get_param('ticket')
        if ticket_id:
            ticket = config.db.downloads.find_one({'_id': ticket_id})
            if not ticket:
                raise APINotFoundException('no such ticket')
            if ticket['ip'] != self.request.client_addr:
                raise APIPermissionException('ticket not for this source IP')
            else:
                self.response.app_iter = downloader.archivestream(ticket)
            self.response.headers['Content-Type'] = 'application/octet-stream'
            self.response.headers['Content-Disposition'] = 'attachment; filename=' + ticket['filename'].encode('ascii', errors='ignore')
        else:

            req_spec = self.request.json_body

            if self.is_true('bulk'):
                return downloader.bulk_preflight_archivestream(req_spec.get('files', []))
            else:
                payload_schema_uri = validators.schema_uri('input', 'download.json')
                validator = validators.from_schema_path(payload_schema_uri)
                validator(req_spec, 'POST')
                return downloader.preflight_archivestream(req_spec, collection=self.get_param('collection'))

    @require_login
    def summary(self):
        """Return a summary of what has been/will be downloaded based on a given query"""
        res = {}
        req = self.request.json_body
        cont_query = {
            'projects': {'_id': {'$in':[]}},
            'sessions': {'_id': {'$in':[]}},
            'acquisitions': {'_id': {'$in':[]}},
            'analyses' : {'_id': {'$in':[]}}
        }
        for node in req:
            node['_id'] = bson.ObjectId(node['_id'])
            level = node['level']

            containers = {'projects':0, 'sessions':0, 'acquisitions':0, 'analyses':0}

            if level == 'project':
                # Grab sessions and their ids
                sessions = config.db.sessions.find({'project': node['_id'], 'deleted': {'$exists': False}}, {'_id': 1})
                session_ids = [s['_id'] for s in sessions]
                acquisitions = config.db.acquisitions.find({'session': {'$in': session_ids}, 'deleted': {'$exists': False}}, {'_id': 1})
                acquisition_ids = [a['_id'] for a in acquisitions]

                containers['projects']=1
                containers['sessions']=1
                containers['acquisitions']=1

                # for each type of container below it will have a slightly modified match query
                cont_query.get('projects',{}).get('_id',{}).get('$in').append(node['_id'])
                cont_query['sessions']['_id']['$in'] = cont_query['sessions']['_id']['$in'] + session_ids
                cont_query['acquisitions']['_id']['$in'] = cont_query['acquisitions']['_id']['$in'] + acquisition_ids

            elif level == 'session':
                acquisitions = config.db.acquisitions.find({'session': node['_id'], 'deleted': {'$exists': False}}, {'_id': 1})
                acquisition_ids = [a['_id'] for a in acquisitions]


                # for each type of container below it will have a slightly modified match query
                cont_query.get('sessions',{}).get('_id',{}).get('$in').append(node['_id'])
                cont_query['acquisitions']['_id']['$in'] = cont_query['acquisitions']['_id']['$in'] + acquisition_ids

                containers['sessions']=1
                containers['acquisitions']=1

            elif level == 'acquisition':

                cont_query.get('acquisitions',{}).get('_id',{}).get('$in').append(node['_id'])
                containers['acquisitions']=1

            elif level == 'analysis':
                cont_query.get('analyses',{}).get('_id',{}).get('$in').append(node['_id'])
                containers['analyses'] = 1

            else:
                self.abort(400, "{} not a recognized level".format(level))

            containers = [cont for cont in containers if containers[cont] == 1]

        for cont_name in containers:
            # Aggregate file types
            pipeline = [
                {'$match': cont_query[cont_name]},
                {'$unwind': '$files'},
                {'$project': {'_id': '$_id', 'type': '$files.type','mbs': {'$divide': ['$files.size', BYTES_IN_MEGABYTE]}}},
                {'$group': {
                    '_id': '$type',
                    'count': {'$sum' : 1},
                    'mb_total': {'$sum':'$mbs'}
                }}
            ]

            try:
                result = config.db.command('aggregate', cont_name, pipeline=pipeline)
            except Exception as e: # pylint: disable=broad-except
                self.log.warning(e)
                self.abort(500, "Failure to load summary")

            if result.get("ok"):
                for doc in result.get("result"):
                    type_ = doc['_id']
                    if res.get(type_):
                        res[type_]['count'] += doc.get('count',0)
                        res[type_]['mb_total'] += doc.get('mb_total',0)
                    else:
                        res[type_] = doc
        return res
