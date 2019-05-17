import time
import uuid
from webob.request import Request

from .. import config
from .. import util
from ..dao import containerutil
from .errors import APIValidationException

AccessType = util.Enum(
    "AccessType",
    {
        "accept_failed_output": "accept_failed_output",
        "delete_container": "delete_container",
        "view_container": "view_container",
        "view_subject": "view_subject",
        "view_file": "view_file",
        "view_job": "view_job",
        "view_job_logs": "view_job_logs",
        "download_file": "download_file",
        "replace_file": "replace_file",
        "delete_file": "delete_file",
        "delete_analysis": "delete_analysis",
        "user_login": "user_login",
        "user_logout": "user_logout",
    },
)
AccessTypeList = [type_name for type_name, member in AccessType.__members__.items()]  # pylint: disable=no-member


class SciTranRequest(Request):
    """Extends webob.request.Request"""

    def __init__(self, *args, **kwargs):
        super(SciTranRequest, self).__init__(*args, **kwargs)
        self.id = "{random_chars}-{timestamp}".format(timestamp=str(int(time.time())), random_chars=str(uuid.uuid4().hex)[:8])
        self.logger = config.log.with_context(request_id=self.id)


def beta_feature(handler_method):
    """A decorator to limit access to an endpoint to clients who set the X-Accept-Feature: beta header"""

    def beta_wrapper(self, *args, **kwargs):
        if not self.is_enabled("beta"):
            raise APIValidationException("Feature not enabled")
        return handler_method(self, *args, **kwargs)

    return beta_wrapper


def log_access(access_type, cont_kwarg="cont_name", cont_id_kwarg="cid", filename_kwarg="name"):
    """
    A decorator to log a user or drone's access to an endpoint
    """

    def log_access_decorator(handler_method):
        def log_user_access_from_request(self, *args, **kwargs):
            result = handler_method(self, *args, **kwargs)

            cont_name = None
            cont_id = None
            filename = None
            job_id = None

            if access_type in [AccessType.view_job, AccessType.view_job_logs]:
                job_id = kwargs.get("_id") or args[0]
            elif access_type not in [AccessType.user_login, AccessType.user_logout]:

                cont_name = kwargs.get(cont_kwarg)
                if cont_name:
                    cont_name = containerutil.singularize(cont_name)
                cont_id = kwargs.get(cont_id_kwarg)
                filename = kwargs.get(filename_kwarg)

                # Only log view_container events when the container is a project/subject/session/acquisition
                if access_type is AccessType.view_container and cont_name not in ["project", "subject", "session", "acquisition"]:
                    return result

                # Make new subject access logs (from /subjects/x) consistent with old logs (from /sessions/x/subject)
                # TODO transition to AccessType.view_container ASAP
                if cont_name == "subject":
                    # Cannot assign access_type for scoping reasons (and nonlocal is py3-only)
                    self.log_user_access(AccessType.view_subject, cont_name=cont_name, cont_id=cont_id, filename=filename)
                    return result

            self.log_user_access(access_type, cont_name=cont_name, cont_id=cont_id, filename=filename, job_id=job_id)

            return result

        return log_user_access_from_request

    return log_access_decorator
