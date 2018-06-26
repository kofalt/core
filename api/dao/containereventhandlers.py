from .. import config
from ..dao.containerevents import register_container_observer

log = config.log

def register():
    """Register global event handlers"""
    # Create jobs when files are updated (any container)
    register_container_observer(create_jobs_event_handler, event_types=['container_files_updated'])

    register_container_observer(update_session_compliance_handler_for_files, 
        cont_types=['session', 'acquisition'], event_types=['container_files_updated'])

    register_container_observer(update_session_compliance_handler_for_acquisition, 
        cont_types=['acquisition'], event_types=['container_created', 'container_updated', 'container_deleted'])

def create_jobs_event_handler(event, result):
    """Handle job creation for container updates (when container files change)"""
    from ..jobs.rules import create_jobs
    if not event.container_before:
        # Don't try to create jobs if we don't have a "before" container
        if isinstance(result, dict):
            result['jobs_spawned'] = 0
        return

    jobs_spawned = create_jobs(config.db, event.container_before, event.container_after, event.container_type)
    result['jobs_spawned'] = len(jobs_spawned)

def update_session_compliance_handler_for_files(event, _):
    """Handle recalculation of session compliance on container updates"""
    from ..dao.containerstorage import SessionStorage, AcquisitionStorage
    if event.container_type == 'sessions':
        session_id = event.container_id
    else:
        session_id = AcquisitionStorage().get_container(event.container_id, projection={'session':True}).get('session')
    SessionStorage().recalc_session_compliance(session_id)

def update_session_compliance_handler_for_acquisition(event, _):
    """Handle recalculation of session compliance when acquisitions are updated"""
    from ..dao.containerstorage import SessionStorage
    session_id = None

    cont = getattr(event, 'container_before', None)
    if not cont:
        cont = getattr(event, 'container_after', None)

    if cont:
        session_id = cont.get('session')

    if not session_id:
        log.warning('Could not get session id for event {}. Session compliance will not be updated'.format(event))
        return

    SessionStorage().recalc_session_compliance(session_id)
