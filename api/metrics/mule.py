""" Metrics Mule Script

This script runs as a separate process in uwsgi, collecting metrics from each worker.
The metrics captured include response codes and timing, as well as various system counters and
database statistics.

References:
    * UWSGI Mules: https://uwsgi-docs.readthedocs.io/en/latest/Mules.html
    * Multiprocess Metrics: https://github.com/prometheus/client_python#multiprocess-mode-gunicorn
"""
import logging
import psutil
import time

from datetime import datetime
from prometheus_client import multiprocess

from api import config
from api.dao import containerstorage
from api.handlers.devicehandler import get_device_statuses
from api.metrics import values

log = logging.getLogger('flywheel.metrics')

# Poll interval in seconds
POLL_INTERVAL = 30

# We're interested in the following CPU time buckets
CPU_TIME_MODES = ['user', 'system', 'idle', 'iowait']

# The set of system memory buckets we're interested in
SYSTEM_MEMORY_TYPES = ['total', 'available', 'used', 'free', 'buffers', 'cached', 'shared']

# The set of per-process memory usage we're interested in
WORKER_MEMORY_TYPES = ['rss', 'vms', 'shared']

# The set of filesystem paths to report usage on
DISK_PATHS = ['/', '/tmp']

# Aggregation pipeline to group jobs by state
JOBS_BY_STATE_QUERY = [{'$group': {
    '_id': '$state',
    'count': {'$sum': 1}
}}] 

# The list of collections to collect raw counts for
COUNT_COLLECTIONS = ['users', 'groups', 'projects', 'sessions']

def collect_system_metrics():
    """Collect system-level metrics (CPU, memory, io and disk usage)"""
    try:
        # Collect global CPU metrics
        cpu_times_pct = psutil.cpu_times_percent()
        for mode in CPU_TIME_MODES:
            value = getattr(cpu_times_pct, mode, None)
            if value is not None:
                values.SYSTEM_CPU_TIMES_PCT.labels(mode).set(value)

        # Collect global Memory metrics
        mem_info = psutil.virtual_memory()
        for typename in SYSTEM_MEMORY_TYPES:
            value = getattr(mem_info, typename, None)
            if value is not None:
                values.SYSTEM_MEMORY_USAGE.labels(typename).set(value)

        # Network I/O stats
        net_info = psutil.net_io_counters()
        values.SYSTEM_NETWORK_BYTES_SENT.set(net_info.bytes_sent)
        values.SYSTEM_NETWORK_BYTES_RECEIVED.set(net_info.bytes_recv)

        # Disk I/O stats
        disk_info = psutil.disk_io_counters()
        values.SYSTEM_DISK_READ_COUNT.set(disk_info.read_count)
        values.SYSTEM_DISK_WRITE_COUNT.set(disk_info.write_count)
        values.SYSTEM_DISK_READ_BYTES.set(disk_info.read_bytes)
        values.SYSTEM_DISK_WRITE_BYTES.set(disk_info.write_bytes)

        for path in DISK_PATHS:
            disk_usage = psutil.disk_usage(path)
            values.SYSTEM_DISK_BYTES_FREE.labels(path).set(disk_usage.free)
            values.SYSTEM_DISK_BYTES_USED.labels(path).set(disk_usage.used)
    except: # pylint: disable=bare-except
        log.exception('Error collecting system metrics')

def collect_worker_metrics(workers):
    """Collect process-level metrics for each worker, and cleanup dead workers.

    Arguments:
        workers (dict): The current set of workers, as a map of pid -> Process
    """
    try:
        import uwsgi

        # For now, just cleanup dead workers
        dead_workers = set(workers.keys())
        for worker in uwsgi.workers():
            pid = worker['pid']

            if pid in dead_workers:
                dead_workers.remove(pid)

            if pid not in workers:
                log.info('Discovered worker process: {}'.format(pid))
                workers[pid] = psutil.Process(pid)

        # Cleanup after dead workers
        for pid in dead_workers:
            log.info('Cleaning up metrics from dead worker {}'.format(pid))
            workers.remove(pid)
            multiprocess.mark_process_dead(pid)

            # Remove any labels for those pids
            values.remove_worker_label(pid)

            # Increment dead worker count
            values.DEAD_WORKERS.inc()

        # Collect metrics for mule processes
        for pid, proc in workers.items():
            with proc.oneshot():
                cpu_pct = proc.cpu_percent()
                mem_info = proc.memory_info()

            values.WORKER_CPU_USAGE.labels(pid).set(cpu_pct)

            for typename in WORKER_MEMORY_TYPES:
                value = getattr(mem_info, typename, None)
                if value is not None:
                    values.WORKER_MEMORY_USAGE.labels(pid, typename).set(value)

    except: # pylint: disable=bare-except
        log.exception('Error collecting worker metrics')

def collect_db_metrics():
    """Collect metrics from mongodb, including version and job states"""
    try:
        # Get version info
        version_info = config.get_version()
        if version_info:
            values.DB_VERSION.set(version_info.get('database', 0))

            release = version_info.get('release', 'UNKNOWN')
            values.RELEASE_VERSION.labels(release).set(1)

        # Get jobs info
        for entry in config.db.jobs.aggregate(JOBS_BY_STATE_QUERY):
            values.JOBS_BY_STATE.labels(entry['_id']).set(entry['count'])

        # Get raw collection counts
        for collection_name in COUNT_COLLECTIONS:
            count = config.db[collection_name].count()
            values.COLLECTION_COUNT.labels(collection_name).set(count)

        # Get gear versions
        gear_count = 0
        for gear_doc in config.db.gears.find():
            gear = gear_doc.get('gear', {})
            name = gear.get('name', 'UNKNOWN')
            version = gear.get('version', 'UNKNOWN')
            created = str(gear_doc.get('created', 'UNKNOWN'))
            values.GEAR_VERSIONS.labels(name, version, created).set(1)
            gear_count = gear_count + 1
        values.COLLECTION_COUNT.labels('gears').set(gear_count)

        # Get devices
        device_count = 0
        device_storage = containerstorage.ContainerStorage('devices', use_object_id=True)
        devices = device_storage.get_all_el(None, None, None)
        device_statuses = get_device_statuses(devices)
        status_counts = {}
        for device in devices:
            device_id = str(device['_id'])
            device_type = device.get('type') or device.get('method') or 'UNKNOWN'
            device_name = device.get('name', 'UNKNOWN')
            last_seen = device.get('last_seen')
            if last_seen:
                since_last_seen = (datetime.now() - last_seen).total_seconds()
            else:
                since_last_seen = -1
            interval = device.get('interval', -1)

            # Set
            device_label = [device_type, device_name, device_id]
            values.DEVICE_TIME_SINCE_LAST_SEEN.labels(*device_label).set(since_last_seen)
            values.DEVICE_INTERVAL.labels(*device_label).set(interval)

            # Increment count by type
            device_status = device_statuses[device_id]['status']
            status_key = (device_type, device_status)
            current_count = status_counts.setdefault(status_key, 0)
            status_counts[status_key] = current_count + 1

            device_count = device_count + 1

        # Device count
        values.COLLECTION_COUNT.labels('devices').set(device_count)

        # Status count
        for label, count in status_counts.items():
            values.DEVICE_STATUS_COUNT.labels(*label).set(count)

    except: # pylint: disable=bare-except
        log.exception('Error collecting db metrics')

def run_mule():
    try:
        import uwsgi
    except ImportError:
        log.warn('Unable to import uwsgi, falling back to poll interval')
        uwsgi = None

    # Find workers
    workers = {}

    while True:
        with values.COLLECT_METRICS_TIME.time():
            collect_system_metrics()
            collect_worker_metrics(workers)
            collect_db_metrics()

        # Wait for next message before polling
        if uwsgi:
            uwsgi.farm_get_msg()
        else:
            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    run_mule()

