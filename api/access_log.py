import datetime

from . import config

from .dao.hierarchy import get_parent_tree
from .web.request import AccessType
from .web.errors import APIStorageException


def log_user_access(request, access_type, cont_name=None, cont_id=None,
                    filename=None, origin=None, download_ticket=None,
                    job_id=None):
    """Create a single access log entry, populating context automatically.

    Only creates one access log entry for multiple downloads of a single file via ticket.
    Context will be created based on passed in container name and id.

    Arguments:
        request (object): The request object
        access_type (AccessType): The access log entry type
        cont_name (str): The name of the container collection being accessed
        cont_id (str): The id of the container being accessed
        filename (str): If this is a file access, the name of the file accessed.
        origin (dict): The request origin (e.g. user id)
        download_ticket (str): The ticket_id if if this is a ticketed file_access

    Raises:
        Exception: If an error occurred creating or inserting the record.
            In the event of an exception, the request MUST BE ABORTED!
    """
    if not config.get_item('core', 'access_log_enabled'):
        return

    context = None
    if access_type in [AccessType.view_job, AccessType.view_job_logs]:
        if job_id is None:
            raise Exception('Job information not available')
        context = {'job': {'id': job_id}}
    elif access_type not in [AccessType.user_login, AccessType.user_logout]:
        if cont_name is None or cont_id is None:
            raise Exception('Container information not available.')

        # Create a context tree for the container
        context = {}

        if cont_name in ['collection', 'collections']:
            context['collection'] = {'id': cont_id}
        else:
            try:
                tree = get_parent_tree(cont_name, cont_id)
            except APIStorageException:
                return

            for k, v in tree.iteritems():
                label_key = 'code' if k == 'subject' else 'label'

                if not v:
                    context[k] = {'id': 'missing', 'label': 'missing or deleted'}
                else:
                    context[k] = {'id': str(v['_id']), 'label': v.get(label_key)}

        if filename:
            context['file'] = {'name': filename}

        if download_ticket:
            context['ticket_id'] = download_ticket

    log_map = create_entry(request, access_type, origin, context)
    config.log_db.access_log.insert_one(log_map)

def create_entry(request, access_type, origin, context=None):
    """Create a single access log entry, without inserting it into the database.

    Only creates one access log entry for multiple downloads of a single file via ticket.
    Context will be created based on passed in container name and id.

    Arguments:
        request (object): The request object
        access_type (AccessType): The access log entry type
        origin (dict): The request origin (e.g. user id)
        context (dict): The context object. MUST BE SPECIFIED for all entries
            except for user_login and user_logout.

    Returns:
        dict: The access log entry, ready for database insertion

    Raises:
        Exception: If a validation error occurred. This is a programmer error that must be fixed!
    """
    if not isinstance(access_type, AccessType):
        raise Exception('Programmer Error: Invalid access type: {}'.format(access_type))

    result = {
        'access_type':      access_type.value,
        'request_method':   request.method,
        'request_path':     request.path,
        'ip':               request.client_addr,
        'origin':           origin,
        'timestamp':        datetime.datetime.utcnow()
    }

    if context is None:
        if access_type not in [AccessType.user_login, AccessType.user_logout]:
            raise Exception('Programmer Error: Log context MUST be specified!')
    else:
        result['context'] = context
        if access_type in [AccessType.view_file, AccessType.download_file, AccessType.replace_file, AccessType.delete_file]:
            if not context.get('file'):
                raise Exception('Programmer Error: File log entries must include file')

    return result

def bulk_log_access(request, origin, entries):
    """Perform a bulk insert of access log entries for a single request.

    For each access_type/context pair in entries a log entry will be created, then inserted in bulk.

    Arguments:
        request (object): The request object
        origin (dict): The request origin (e.g. user id)
        entries (list): A list of tuples of (access_type, context)

    Raises:
        Exception: If an error occurred creating or inserting the records.
            In the event of an exception, the request MUST BE ABORTED!
    """
    bulk = config.log_db.access_log.initialize_unordered_bulk_op()

    for access_type, context in entries:
        log_map = create_entry(request, access_type, origin, context=context)
        bulk.insert(log_map)

    bulk.execute()

