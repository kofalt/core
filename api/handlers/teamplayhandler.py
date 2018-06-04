import datetime
import hashlib
import hmac

import bson
import requests

from ..auth import require_drone
from .. import config
from ..web import base, errors


class TeamplayHandler(base.RequestHandler):

    def echo(self):
        """Return `echo` query param's value in plaintext. (see teamplay webhook spec)"""
        self.response.write(self.request.GET.get('echo'))

    def event(self):
        """Create event doc in mongo from payload as-is. (see teamplay webhook spec)"""
        try:
            teamplay_config = config.get_auth('teamplay')
            secret = bytes(teamplay_config['webhook_secret'])
        except KeyError:
            self.abort(503, 'Teamplay DICOM Webhook not configured')

        expected_hash = self.request.headers.get('ms-signature', '').replace('sha256=', '')
        computed_hash = hmac.new(secret, msg=self.request.body, digestmod=hashlib.sha256).hexdigest()
        if computed_hash != expected_hash:
            self.abort(401, 'Invalid signature')
        result = config.db.teamplay.insert_one(self.request.json_body)
        if not result.acknowledged:
            raise errors.APINotFoundException('Could not create queue item')
        return {'_id': result.inserted_id}

    @require_drone
    def get_token(self):
        """Get and return app JWT to be used by reaper. (see teamplay auth spec)"""
        try:
            teamplay_config = config.get_auth('teamplay')
        except KeyError:
            self.abort(503, 'Teamplay SSO not configured')

        response = requests.post(teamplay_config['token_endpoint'],
            headers={
                'Ocp-Apim-Subscription-Key': teamplay_config['client_secret'],
            },
            data={
                'grant_type': 'client_credentials',
                'client_id': teamplay_config['client_id'],
                'client_secret': teamplay_config['client_secret'],
            }
        )
        token = response.json()
        return token

    @require_drone
    def get_queue(self):
        """Return teamplay event reap queue"""
        return config.db.teamplay.find({'deleted': {'$exists': False}})

    @require_drone
    def reap_item(self, _id):
        """Remove teamplay event from reap queue"""
        result = config.db.teamplay.update_one({'_id': bson.ObjectId(_id)}, {'$set': {'deleted': datetime.datetime.utcnow()}})
        if result.modified_count != 1:
            raise errors.APINotFoundException('Could not find queue item ' + _id)
        return {'deleted': 1}


    def ping(self):
        """
        Return HTTP 200 Status Code when service is reachable through the network
          - Teamplay documentation
        """
        return

    def is_operable(self):
        """
        To detect whether the service is fully functional so that the integration will work for teamplay customers.
          - Teamplay documentation

        Assert proper config and service availability for:
          - Teamplay auth conifg
          - Teamplay webhook config
          - Reaper availability
          - Others?
        """
        err = []
        cfg = config.get_config()

        if 'teamplay' not in cfg['auth']:
            err.append('Teamplay SSO not configurated.')
        elif 'webhook_secret' not in cfg['auth']['teamplay']:
            err.append('Teamplay DICOM Webhook not configurated.')

        # Test reaper here

        if err:
            self.response.status = 503
            return {'Reason': ' '.join(err)}

        return {}
