from ... import config


class VirusScanMapper(object):
    """Data mapper for virus scan trigger."""

    def __init__(self, db=None):
        self.db = db or config.db

    def get_unsent_files(self):
        cont_names = ['projects', 'subjects', 'sessions', 'acquisitions', 'analyses', 'collections']

        for cont_name in cont_names:
            cursor = self.db.get_collection(cont_name).aggregate(FILES_CNT_PIPELINE)
            for f in cursor:
                f['parent_type'] = cont_name
                yield f


FILES_CNT_PIPELINE = [
    {
        '$match': {
            'deleted': {'$exists': False}
        }
    },
    {'$unwind':'$files'},
    {
        '$addFields': {'files.parent_id' : '$_id'}
    },
    {'$replaceRoot': {'newRoot': '$files'}},
    {
        '$match': {
            '$and': [
                {'deleted': {'$exists': False}},
                {'virus_scan.state': {'$eq': 'quarantined'}},
                {'virus_scan.webhook_sent': {'$eq': False}}
            ]
        }
    }
]
