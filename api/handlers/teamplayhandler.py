import datetime
import hashlib
import hmac

import bson
import requests

from ..auth import require_drone
from .. import config
from ..web import base, errors


class TeamplayHandler(base.RequestHandler):

    @property
    def config(self):
        return config.get_auth('teamplay')

    def echo(self):
        """Return `echo` query param's value in plaintext. (see teamplay webhook spec)"""
        self.response.write(self.request.GET.get('echo'))

    def event(self):
        """Create event doc in mongo from payload as-is. (see teamplay webhook spec)"""
        secret = bytes(self.config['webhook_secret'])
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
        response = requests.post(self.config['token_endpoint'],
            headers={
                'Ocp-Apim-Subscription-Key': self.config['api_key']
            },
            data={
                'grant_type': 'client_credentials',
                'client_id': self.config['client_id'],
                'client_secret': self.config['client_secret'],
            }
        )
        token = response.json()
        return token

    @require_drone
    def get_queue(self):
        """"""
        return config.db.teamplay.find({'deleted': {'$exists': False}})

    @require_drone
    def reap_item(self, _id):
        """"""
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

        try:
            config.get_auth('teamplay')
        except KeyError:
            err.append('Teamplay SSO not configurated.')

        try:
            config.get_item('teamplay', 'webhook_secret')
        except KeyError:
            err.append('Teamplay DICOM Webhook not configurated.')

        # Test reaper here

        if err:
            return {'Reason': ' '.join(err)}
        else:
            return {}

