# Metrics values 
from prometheus_client import Summary, Gauge, Counter

# ===== Request Handlers =====
# Labels: Method, Path, Code

# Response Time
RESPONSE_TIME = Summary('response_time_seconds', 'Observed time to complete response, in seconds', ['method', 'template', 'status'])
# Response Size
RESPONSE_SIZE = Summary('response_size_bytes', 'Observed response size, in bytes', ['method', 'template', 'status'])

# ===== Search =====
ELASTIC_VERSION = Gauge('elastic_version', 'The elastic version info', ['build_hash', 'lucene_version', 'version'], multiprocess_mode='livesum')
ELASTIC_IS_UP = Gauge('elastic_is_up', 'Whether or not elastic is up, 1 for alive, 0 for dead', [], multiprocess_mode='livesum')

# ===== UWSGI Workers ======
# Labels: PID

# CPU Usage
WORKER_CPU_USAGE = Gauge('worker_cpu_usage_percent', 'Observed cpu usage as a percentage', ['worker_pid'], multiprocess_mode='livesum')
# Memory Usage
WORKER_MEMORY_USAGE = Gauge('worker_memory_usage_bytes', 'Observed memory usage in bytes by type', ['worker_pid', 'type'], multiprocess_mode='livesum')
# Total worker deaths
DEAD_WORKERS = Counter('worker_deaths', 'Number of workers that died unexpectedly', [])

def remove_worker_label(pid):
    """Cleanup worker stats by PID

    Arguments:
        pid (string): The worker process id
    """
    WORKER_CPU_USAGE.remove(pid)
    WORKER_MEMORY_USAGE.remove(pid)

# ===== System =====
# Global cpu time by mode
SYSTEM_CPU_TIMES_PCT = Gauge('system_cpu_times_percent', 'Observed cpu times as percent time spent in mode', ['mode'], multiprocess_mode='livesum')
# Global memory usage
SYSTEM_MEMORY_USAGE = Gauge('system_memory_usage_bytes', 'Observed system memory usage, in bytes', ['type'], multiprocess_mode='livesum')
# Network I/O
SYSTEM_NETWORK_BYTES_SENT = Gauge('system_network_bytes_sent', 'Observed network bytes sent', [], multiprocess_mode='max')
SYSTEM_NETWORK_BYTES_RECEIVED = Gauge('system_network_bytes_received', 'Observed network bytes received', [], multiprocess_mode='max')
# Disk I/O
SYSTEM_DISK_READ_COUNT = Gauge('system_disk_read_count', 'Observed disk read count', [], multiprocess_mode='max')
SYSTEM_DISK_WRITE_COUNT = Gauge('system_disk_write_count', 'Observed disk write count', [], multiprocess_mode='max')
SYSTEM_DISK_READ_BYTES = Gauge('system_disk_read_bytes', 'Observed disk read bytes', [], multiprocess_mode='max')
SYSTEM_DISK_WRITE_BYTES = Gauge('system_disk_write_bytes', 'Observed disk write bytes', [], multiprocess_mode='max')
# Disk Usage
SYSTEM_DISK_BYTES_USED = Gauge('system_disk_bytes_used', 'Observed disk usage, in bytes', ['path'], multiprocess_mode='max')
SYSTEM_DISK_BYTES_FREE = Gauge('system_disk_bytes_free', 'Observed disk availability, in bytes', ['path'], multiprocess_mode='max')

# ===== DB Stats =====
# DB Version
DB_VERSION = Gauge('db_version', 'The database version', [], multiprocess_mode='livesum')
# App Version
RELEASE_VERSION = Gauge('release_version', 'The app release version', ['version'], multiprocess_mode='livesum')
# Job Counts (label=state)
JOBS_BY_STATE = Gauge('job_counts_by_state', 'Total number of jobs in each state', ['state'], multiprocess_mode='livesum')
# Counts: Users, Groups, Projects, Subjects, Sessions
COLLECTION_COUNT = Gauge('collection_counts', 'Total number of documents in each collection', ['collection'], multiprocess_mode='livesum')

# ===== Meta =====
COLLECT_METRICS_TIME = Summary('collect_metrics_time_seconds', 'Observed time to collect metrics, in seconds', [])
