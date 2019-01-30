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

# ===== DB Stats =====
# DB Version
DB_VERSION = Gauge('fw_core_db_version', 'The database version', [], multiprocess_mode='max')
# App Version
RELEASE_VERSION = Gauge('fw_core_release_version', 'The app release version', ['version'], multiprocess_mode='max')
# Job Counts (label=state)
JOBS_BY_STATE = Gauge('fw_core_jobs', 'Total number of jobs in each state', ['state'], multiprocess_mode='max')
# Gear versions
GEAR_VERSIONS = Gauge('fw_core_gear', 'Number of jobs for a gear name, version and created', ['name', 'version', 'created'], multiprocess_mode='max')
# Counts: Users, Groups, Projects, Subjects, Sessions, Gears, Devices
COLLECTION_COUNT = Gauge('fw_core_collection_count', 'Total number of documents in each collection', ['collection'], multiprocess_mode='max')
# Device last seen
DEVICE_TIME_SINCE_LAST_SEEN = Gauge('fw_core_device_since_last_seen_seconds', 'Time since a device was last seen, in seconds', ['type', 'name', 'id'], multiprocess_mode='max')
# Device interval
DEVICE_INTERVAL = Gauge('fw_core_device_interval_seconds', 'The device interval, in seconds', ['type', 'name', 'id'], multiprocess_mode='max')
# Total number of active / passive devices
DEVICE_STATUS_COUNT = Gauge('fw_core_device_status_counts', 'The number of devices by type and status', ['type', 'status'], multiprocess_mode='max')
# Total number of logins
USER_LOGIN_COUNT = Gauge('fw_core_user_login_count', 'The number of access logs of type user_login', [], multiprocess_mode='max')
# Last Event Timestamps: events: session_created, user_login, job_queued[_by_system, by_user]
LAST_EVENT_TIME = Gauge('fw_core_last_event_time', 'The seconds since an event as happened', ['event'], multiprocess_mode='max')

# ===== Meta =====
COLLECT_METRICS_TIME = Summary('fw_core_collect_metrics_time_seconds', 'Observed time to collect metrics, in seconds', [])

