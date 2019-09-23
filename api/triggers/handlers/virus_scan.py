"""Resend failed webhooks for quarantined files."""
from ... import config
from ...dao import containerutil, liststorage
from ...web import base, errors
from ...webhooks import VirusScanWebhook
from .. import mappers


class VirusScanTriggerHandler(base.RequestHandler):
    def post(self):
        if not config.get_feature('virus_scan', False):
            return

        callback_url = config.get_config()['webhooks']['virus_scan']
        if not callback_url:
            msg = 'Callback url for virus scan webhook is not configured.'
            config.log.critical(msg)
            raise errors.APIException(msg)
        webhook = VirusScanWebhook(callback_url)
        mapper = mappers.VirusScanMapper()
        files = mapper.get_unsent_files()
        for f in files:
            storage = liststorage.FileStorage(f['parent_type'])
            webhook.call(file_info=f, parent={
                'type': containerutil.singularize(f['parent_type']),
                '_id': f['parent_id']
            }, raise_for_status=True)
            # udpate file's webhook sent state in db
            storage.exec_op('PUT', _id=f['parent_id'], query_params={
                'name': f['name']
            }, payload={
                'virus_scan.webhook_sent': True
            })
