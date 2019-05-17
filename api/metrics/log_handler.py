import logging
from .values import LOG_MESSAGE_COUNT


class MetricsLogHandler(logging.Handler):
    """Log handler that increments a logging metrics counter"""

    def __init__(self, level=logging.WARN):  # pylint: disable=useless-super-delegation
        """Create a new MetricsLogHandler

		Arguments:
			level (int): The log-level threshold
		"""
        super(MetricsLogHandler, self).__init__(level)

    def emit(self, record):
        """Increment the counter"""
        LOG_MESSAGE_COUNT.labels(record.name, record.levelname).inc()
