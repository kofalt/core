"""
Maintains (via Map/Reduce) a map of job ids to gear details.
This collection exists largely to support joining file origin 
to gear version for the billing report.
"""
import datetime

from .. import config

log = config.log

def update_file_job_origin():
    """Update the file_job_origin collection ensuring that it contains all jobs"""
    # Map to string id, include creation date and gear info
    map_fn = '''
        function() {
            var key = "" + this._id;
            var value = {
                created: this.created,
                gear_info: this.gear_info
            };
            emit(key, value);
        }
    '''
    # No-op reduce, since we have unique records
    reduce_fn = 'function() {}'
    out = { 'merge': 'file_job_origin' } 

    # For performance, only merge in jobs that were created after the last run
    start = datetime.datetime.now()
    query = {}
    last_rec = config.db.file_job_origin.find_one({}, sort=[('created', -1)])
    if last_rec:
        query['created'] = {'$gt': last_rec['value']['created']}

    log.info('Updating file_job_origin collection')
    config.db.jobs.map_reduce(map_fn, reduce_fn, out, query=query)
    end = datetime.datetime.now()

    log.info('Updated file_job_origin collection in %4.2f seconds', (end-start).total_seconds())
