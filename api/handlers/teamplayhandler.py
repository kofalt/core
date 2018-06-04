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
        config.get_auth('teamplay')

    def echo(self):
        """Return `echo` query param value in plaintext. (see teamplay webhook spec)"""
        def echo_handler(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
            return self.request.GET.get('echo')
        return echo_handler

    def event(self):
        """Create event doc in mongo from payload as-is. (see teamplay webhook spec)"""
        secret = config.get_item('teamplay', 'webhook_secret')
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
        result = config.db.teamplay.update_one({'_id': bson.ObjectId(_id)}, {'deleted': datetime.datetime.utcnow()})
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
        errors = []

        try:
            config.get_auth('teamplay')
        except KeyError:
            errors.append('Teamplay SSO not configurated.')

        try:
            config.get_item('teamplay', 'webhook_secret')
        except KeyError:
            errors.append('Teamplay DICOM Webhook not configurated.')

        # Test reaper here

        if errors:
            return {'Reason': ' '.join(errors)}
        else:
            return {}

