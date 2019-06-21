# Metrics values
from prometheus_client import Summary, Gauge, Counter


#
# IMPORTANT: All metrics should be unified under the component name, in this case 'fw_core'.
#            Please adhere to this grouping so that the source of metrics are clear.
#
prefix = 'fw_core_'


# ===== Request Handlers =====
# Labels: Method, Path, Code

# Response Time
RESPONSE_TIME = Counter(prefix + 'response_time_seconds_sum', 'Observed time to complete response, in seconds', ['method', 'template', 'status'])

# Response Size
RESPONSE_SIZE = Counter(prefix + 'response_size_bytes_sum', 'Observed response size, in bytes', ['method', 'template', 'status'])

# Response Count
RESPONSE_COUNT = Counter(prefix + 'response_count', 'Observed response counts', ['method', 'template', 'status'])

# Log Counter
LOG_MESSAGE_COUNT = Counter(prefix + 'log_message_count', 'Observed log statement counts', ['name', 'level'])


# ===== DB Stats =====

# DB Version
DB_VERSION = Gauge(prefix + 'db_version', 'The database version', [], multiprocess_mode='livesum')

# DB Size
DB_DATA_SIZE = Gauge(prefix + 'db_data_size', 'The total size of uncompressed data in the database', [], multiprocess_mode='livesum')

# DB Size on disk
DB_STORAGE_SIZE = Gauge(prefix + 'db_storage_size', 'The total amount of space allocated to collections in the database', [], multiprocess_mode='livesum')

# DB Total Object Count
DB_OBJECTS = Gauge(prefix + 'db_objects', 'The total count of objects across all collections in the database', [], multiprocess_mode='livesum')

# Api Version
RELEASE_VERSION = Gauge(prefix + 'release_version', 'The api release version', ['version'], multiprocess_mode='livesum')

# App Version
FLYWHEEL_VERSION = Gauge(prefix + 'flywheel_version', 'The app release version', ['version'], multiprocess_mode='livesum')

# Job Counts (label=state)
JOBS_BY_STATE = Gauge(prefix + 'job_stats', 'Total number of jobs in each state', ['state'], multiprocess_mode='livesum')

# Oldest Pending Job (in seconds)
OLDEST_PENDING_JOB = Gauge(prefix + 'oldest_pending_job', 'The oldest pending job\'s creation date, in seconds UTC since epoch', [], multiprocess_mode='livesum')

# Gear versions
GEAR_VERSIONS = Gauge(prefix + 'gear', 'Number of jobs for a gear name, version and created', ['name', 'version', 'created'], multiprocess_mode='livesum')

# Auth provider types
AUTH_PROVIDER_TYPES = Gauge(prefix + 'auth_provider', 'Set if auth provider of type is enabled', ['type'], multiprocess_mode='livesum')

# Collection document count
COLLECTION_COUNT = Gauge(prefix + 'collection_count', 'Total number of documents in a collection', ['collection'], multiprocess_mode='livesum')

# Total collection size
COLLECTION_SIZE = Gauge(prefix + 'collection_size', 'Total uncompressed size in memory of all documents in a collection', ['collection'], multiprocess_mode='livesum')

# Total collection size on disk
COLLECTION_STORAGE_SIZE = Gauge(prefix + 'collection_storage_size', 'Total amount of storage allocated to this collection', ['collection'], multiprocess_mode='livesum')

# Individual index size
COLLECTION_INDEX_SIZE = Gauge(prefix + 'collection_index_size', 'Total size of an index on this collection', ['collection', 'name'], multiprocess_mode='livesum')

# Total collection index size
COLLECTION_TOTAL_INDEX_SIZE = Gauge(prefix + 'collection_total_index_size', 'Total size of all indexes on this collection', ['collection'], multiprocess_mode='livesum')

# Device last seen
DEVICE_TIME_SINCE_LAST_SEEN = Gauge(prefix + 'device_since_last_seen_seconds', 'Time since a device was last seen, in seconds', ['type', 'name', 'id'], multiprocess_mode='livesum')

# Device interval
DEVICE_INTERVAL = Gauge(prefix + 'device_interval_seconds', 'The device interval, in seconds', ['type', 'name', 'id'], multiprocess_mode='livesum')

# Total number of active / passive devices
DEVICE_STATUS_COUNT = Gauge(prefix + 'device_status_counts', 'The number of devices by type and status', ['type', 'status'], multiprocess_mode='livesum')

# Total number of logins
USER_LOGIN_COUNT = Gauge(prefix + 'user_login_count', 'The number of access logs of type user_login', [], multiprocess_mode='livesum')

# Last Event Timestamps: events: session_created, user_login, job_queued[_by_system, by_user]
LAST_EVENT_TIME = Gauge(prefix + 'last_event_time', 'The seconds since an event as happened', ['event'], multiprocess_mode='livesum')

# ===== Meta =====
COLLECT_METRICS_TIME = Summary(prefix + 'collect_metrics_time_seconds', 'Observed time to collect metrics, in seconds', [])

