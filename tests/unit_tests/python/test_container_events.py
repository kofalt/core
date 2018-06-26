import pytest

from api.dao import containerevents
from api.dao.containerevents import ContainerEvent, ContainerEventType, ContainerObserver

def test_container_event_factory():
    event = ContainerEvent.factory(ContainerEventType.container_created, 'group', 'scitran')
    assert event is not None
    assert event.event_type == ContainerEventType.container_created
    assert event.container_name == 'group'
    assert event.container_id == 'scitran'

    event = ContainerEvent.factory('container_updated', 'sessions', 'session1', container_before={'label': 'Session 1'})
    assert event is not None
    assert event.event_type == ContainerEventType.container_updated
    assert event.container_name == 'session'
    assert event.container_id == 'session1'
    assert event.container_before == {'label': 'Session 1'}

    try:
        ContainerEvent.factory('container_reticulated', 'group', 'scitran')
        pytest.fail('Expected Error creating container event with invalid value')
    except KeyError:
        pass

def test_container_observer():
    event = ContainerEvent.factory('container_created', 'sessions', 'session1')

    observer = ContainerObserver(None, None, None)
    assert observer.is_subscribed(event)

    observer = ContainerObserver(None, ['groups'], ['container_created'])
    assert not observer.is_subscribed(event)

    observer = ContainerObserver(None, ['sessions'], ['container_updated'])
    assert not observer.is_subscribed(event)

    observer = ContainerObserver(None, ['session'], ['container_created'])
    assert observer.is_subscribed(event)

def test_container_observer():
    _handled_events = []
    def handle(event, result):
        _handled_events.append(event)

    registry = containerevents.ContainerObserverRegistry()
    registry.register(handle, ['groups'], ['container_deleted'])

    event = ContainerEvent.factory('container_files_updated', 'session', 'session1', container_before={})
    registry.notify(event, {})

    assert not _handled_events

    event = ContainerEvent.factory('container_deleted', 'groups', 'scitran')
    registry.notify(event, {})

    assert len(_handled_events) == 1
    last_event = _handled_events[-1]
    assert last_event is not None
    assert last_event.event_type == ContainerEventType.container_deleted
    assert last_event.container_name == 'group'
    assert last_event.container_id == 'scitran'

