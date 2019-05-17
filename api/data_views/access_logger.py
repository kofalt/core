from ..dao import containerutil

from .. import config
from ..access_log import bulk_log_access
from ..web.request import AccessType

# List of potentially logged events, by container
EVENT_LIST = [("project", AccessType.view_container), ("session", AccessType.view_container), ("subject", AccessType.view_subject), ("acquisition", AccessType.view_container)]


def create_access_logger():
    """Create an access logger instance, returning a no-op logger if access log is disabled"""
    if config.get_item("core", "access_log_enabled"):
        return AccessLogger()

    return AccessLoggerNoop()


def is_phi_field(cont_type, field):
    """Check if the given field is potentially accessing PHI
    
    Arguments:
        cont_type (str): The container type
        field (str): The field name

    Returns:
        bool: True if the field potentially contains PHI
    """
    if cont_type == "subject":
        return True

    next_part = field.split(".")[0]
    if next_part in ["subject", "info", "notes", "tags"]:
        return True

    return False


class AccessLogger(object):
    """Collects access logs for bulk data access"""

    def __init__(self):
        self.file_container = None
        self.containers = set()
        self.context = {}

        self._bulk_entries = []

    def set_file_container(self, cont_name):
        """Set the container where file access will occur
        
        Arguments:
            cont_name (str): The name of the container
        """
        self.file_container = cont_name

    def add_container(self, cont_name):
        """Add a container to the list of containers to be logged
        
        Arguments:
            cont_name (str): The name of the container
        """
        self.containers.add(cont_name)

    def extract_context(self, cont, label_key="label"):
        """Extracts context fields from the given container object.

        Arguments:
            cont (dict): The container object
            label_key (str): The key to use for the `label` property (default is "label")
        
        Returns:
            dict: The context object
        """
        result = {"id": str(cont["_id"])}

        if label_key in cont:
            result["label"] = cont[label_key]

        return result

    def create_context(self, context):
        """Create and store the initial context from a hierarchy tree.

        Arguments:
            context (list): The hierarchy tree
        """
        for cont in context:
            cont_type = containerutil.singularize(cont["cont_type"])
            label_key = "code" if cont_type == "subject" else "label"
            self.context[cont_type] = self.extract_context(cont, label_key=label_key)

    def add_entries(self, context, filename=None):
        """Create bulk entries for each accessed container.

        Arguments:
            context (dict): The log context from bulk retrieval.
            filename (str): The file being accessed, if applicable
        """
        log_context = self.context.copy()

        for cont_type, access_type in EVENT_LIST:
            cont = context.get(cont_type)
            if cont:
                log_context[cont_type] = self.extract_context(cont)

            if cont_type in self.containers:
                # Add log entry
                self._bulk_entries.append((access_type, log_context.copy()))

        if filename:
            log_context["file"] = {"name": filename}
            self._bulk_entries.append((AccessType.download_file, log_context))

    def write_logs(self, request, origin):
        """Write all of the bulk entries created by add_entries calls

        Arguments:
            request (object): The request object
            origin (dict): The request origin (e.g. calling user)
        """
        if self._bulk_entries:
            bulk_log_access(request, origin, self._bulk_entries)


class AccessLoggerNoop(object):
    def set_file_container(self, cont_name):
        pass

    def add_container(self, cont_name):
        pass

    def create_context(self, context):
        pass

    def add_entries(self, context, filename=None):
        pass

    def write_logs(self, request, origin):
        pass

    def is_phi_field(self, _cont_type, _field):
        return False
