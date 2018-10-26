# Metrics values 
from prometheus_client import Summary, Gauge, Counter

# ===== Request Handlers =====
# Labels: Method, Path, Code

# Response Time
RESPONSE_TIME = Counter('fw_core_response_time_seconds_sum', 'Observed time to complete response, in seconds', ['method', 'template', 'status'])
# Response Size
RESPONSE_SIZE = Counter('fw_core_response_size_bytes_sum', 'Observed response size, in bytes', ['method', 'template', 'status'])
# Response Count
RESPONSE_COUNT = Counter('fw_core_response_count', 'Observed response counts', ['method', 'template', 'status'])
# Log Counter
LOG_MESSAGE_COUNT = Counter('fw_core_log_message_count', 'Observed log statement counts', ['name', 'level'])

# ===== System =====
# Global cpu time by mode
SYSTEM_CPU_TIMES_PCT = Gauge('uwsgi_system_cpu_times_percent', 'Observed cpu times as percent time spent in mode', ['mode'], multiprocess_mode='livesum')
# Global memory usage
SYSTEM_MEMORY_USAGE = Gauge('uwsgi_system_memory_usage_bytes', 'Observed system memory usage, in bytes', ['type'], multiprocess_mode='livesum')
# Network I/O
SYSTEM_NETWORK_BYTES_SENT = Gauge('uwsgi_system_network_bytes_sent', 'Observed network bytes sent', [], multiprocess_mode='max')
SYSTEM_NETWORK_BYTES_RECEIVED = Gauge('uwsgi_system_network_bytes_received', 'Observed network bytes received', [], multiprocess_mode='max')
# Disk I/O
SYSTEM_DISK_READ_COUNT = Gauge('uwsgi_system_disk_read_count', 'Observed disk read count', [], multiprocess_mode='max')
SYSTEM_DISK_WRITE_COUNT = Gauge('uwsgi_system_disk_write_count', 'Observed disk write count', [], multiprocess_mode='max')
SYSTEM_DISK_READ_BYTES = Gauge('uwsgi_system_disk_read_bytes', 'Observed disk read bytes', [], multiprocess_mode='max')
SYSTEM_DISK_WRITE_BYTES = Gauge('uwsgi_system_disk_write_bytes', 'Observed disk write bytes', [], multiprocess_mode='max')
# Disk Usage
SYSTEM_DISK_BYTES_USED = Gauge('uwsgi_system_disk_bytes_used', 'Observed disk usage, in bytes', ['path'], multiprocess_mode='max')
SYSTEM_DISK_BYTES_FREE = Gauge('uwsgi_system_disk_bytes_free', 'Observed disk availability, in bytes', ['path'], multiprocess_mode='max')
# Timeout errors
SYSTEM_TIMEOUT_ERROR_COUNT = Counter('uwsgi_timeout_errors', 'Observed TIMEOUT errors', [])
SYSTEM_CONNECTION_RESET_COUNT = Counter('uwsgi_connection_resets', 'Observed Connection reset errors', [])

# ===== DB Stats =====
# DB Version
DB_VERSION = Gauge('fw_db_version', 'The database version', [], multiprocess_mode='livesum')
# App Version
RELEASE_VERSION = Gauge('fw_release_version', 'The app release version', ['version'], multiprocess_mode='livesum')
# Job Counts (label=state)
JOBS_BY_STATE = Gauge('fw_jobs', 'Total number of jobs in each state', ['state'], multiprocess_mode='livesum')
# Gear versions
GEAR_VERSIONS = Gauge('fw_gear', 'Gear name, version and created', ['name', 'version', 'created'], multiprocess_mode='livesum')
# Counts: Users, Groups, Projects, Subjects, Sessions, Gears, Devices
COLLECTION_COUNT = Gauge('fw_collection_count', 'Total number of documents in each collection', ['collection'], multiprocess_mode='livesum')
# Device last seen
DEVICE_TIME_SINCE_LAST_SEEN = Gauge('fw_device_since_last_seen_seconds', 'Time since a device was last seen, in seconds', ['type', 'name', 'id'], multiprocess_mode='livesum')
# Device interval
DEVICE_INTERVAL = Gauge('fw_device_interval_seconds', 'The device interval, in seconds', ['type', 'name', 'id'], multiprocess_mode='livesum')
# Total number of active / passive devices
DEVICE_STATUS_COUNT = Gauge('fw_device_status_counts', 'The number of devices by type and status', ['type', 'status'], multiprocess_mode='livesum')

# ===== Meta =====
COLLECT_METRICS_TIME = Summary('uwsgi_collect_metrics_time_seconds', 'Observed time to collect metrics, in seconds', [])

