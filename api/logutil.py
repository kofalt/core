import collections
import logging

class LoggerContextAdapter(logging.LoggerAdapter):
    """Class that provides syntactic sugar for adding context to a log"""
    def __init__(self, logger, extra=None):
        if extra is None:
            extra = collections.OrderedDict()

        super(LoggerContextAdapter, self).__init__(logger, extra)

    def process(self, msg, kwargs):
        # How we do this could change, for now just append extras to the message in the order declared
        msg = str(msg)
        for context_value in self.extra.items():
            msg += (' %s=%s' % context_value)
        return msg, kwargs

    def with_context(self, **kwargs):
        """Create a new logger, setting the extra attributes specified by kwargs
        
        Arguments:
            **kwargs: The key-value pairs to set as extra

        Returns:
            LoggerContextAdapter: The new logger with context
        """
        context = self.extra.copy()
        context.update(kwargs)
        return LoggerContextAdapter(self.logger, context)

    # ===== Methods not Overridden in python 2.7 =====
    def setLevel(self, level):
        """Set the specified level on the underlying logger."""
        self.logger.setLevel(level)

    def warn(self, msg, *args, **kwargs):
        """
        Delegate a warning call to the underlying logger, after adding
        contextual information from this adapter instance.
        """
        msg, kwargs = self.process(msg, kwargs)
        self.logger.warning(msg, *args, **kwargs)

def getContextLogger(name=None):
    """Get a LoggerAdapter that supports adding context.

    Arguments:
        name (str): The logger name
    """
    return LoggerContextAdapter(logging.getLogger(name))
