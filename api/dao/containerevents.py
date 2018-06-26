""" Container Events """
import collections
from .. import util
from ..web.errors import APINotFoundException

from .containerutil import singularize, pluralize

ContainerEventType = util.Enum('ContainerEventType', {
    'container_created':        'container_created',        # A new container was created
    'container_updated':        'container_updated',        # A container was modified
    'container_deleted':        'container_deleted' ,       # A container was deleted
    'container_files_updated':  'container_files_updated'   # Files on a container were modified (created, updated or deleted)
})

# ===== Container Observer Registry =====
class ContainerObserverRegistry(object):
    def __init__(self):
        """Class that registers and notifies container event listeners"""
        self._observers = []

    def register(self, handler, cont_types, event_types):
        """Register a new event listener that watches cont_types for event_types.

        If cont_types is None or empty, then all containers will be watched.
        If event_types is None or empty, then all events will be watched.

        Arguments:
            handler (function): The handler function that takes an event and response object.
            cont_types (list): A list of containers names to watch (e.g. ['sessions', 'acquisitions'])
            event_types (list): A list  of events to watdch
        """
        self._observers.append(ContainerObserver(handler, cont_types, event_types))

    def notify(self, event, result):
        """Notify all registered observers of with event.

        Arguments:
            event (ContainerEvent): The event that has occurred.
            result (dict): The result object to update, if any updates are required.
        """
        for observer in self._observers:
            # Explicitly allow exceptions to pass through
            if observer.is_subscribed(event):
                observer.handle(event, result)

_registry = ContainerObserverRegistry()

def register_container_observer(handler, cont_types=None, event_types=None):
    """Register a new global event listener that watches cont_types for event_types.

    If cont_types is None or empty, then all containers will be watched.
    If event_types is None or empty, then all events will be watched.

    Arguments:
        handler (function): The handler function that takes an event and response object.
        cont_types (list): A list of containers names to watch (e.g. ['sessions', 'acquisitions'])
        event_types (list): A list  of events to watdch
    """
    _registry.register(handler, cont_types, event_types)

def notify_container_observers(result, container_name, event_type, container_id, **kwargs):
    """Notify all registered observers of a container event

    Arguments:
        result (dict): The result object to update, if any updates are required.
        container_name (str): The name of the container where the event occurred.
        event_type (str): The type of event that occurred
        container_id: The container id (may be an ObjectId or string)
        **kwargs: Additional arguments to pass to each event

    Returns:
        dict: The updated result object
    """
    event = ContainerEvent.factory(event_type, container_name, container_id, **kwargs)
    _registry.notify(event, result)
    return result

# ===== Container Observer =====
class ContainerObserver(object):
    def __init__(self, handler, cont_types, event_types):
        """Helper class that encapsulates event filter and handling.

        Arguments:
            handler (function): The handler function that takes an event and result object
            cont_types (list): The list of container types to accept
            event_types (list): The list of event types to accept
        """
        self._handler = handler

        if cont_types is not None:
            self._cont_types = set([singularize(cont_name) for cont_name in cont_types])
        else:
            self._cont_types = set()

        if event_types is not None:
            self._event_types = set([ContainerEvent.normalize_event_type(event_type) for event_type in event_types])
        else:
            self._event_types = set()

    def handle(self, event, result):
        """Handle an event after is_subscribed returns True

        Arguments:
            event (ContainerEvent): The container event object
            result (dict): The result object to update
        """
        self._handler(event, result)

    def is_subscribed(self, event):
        """Test if this observer is subscribed for the given event

        Arguments:
            event (ContainerEvent): The event

        Returns:
            bool: True if this observer is subscribed for the event, False otherwise
        """
        if self._cont_types and event.container_name not in self._cont_types:
            return False
        if self._event_types and event.event_type not in self._event_types:
            return False
        return True

# ===== Container Events =====
class ContainerEvent(object):
    """Base class for all ContainerEventS"""
    def __init__(self, container_name, container_id):
        """ Initialize container event 
        Arguments:
            container_name (str): The container name
            container_id: The container id
        """
        self._container_name = container_name
        self._container_id = container_id

    def __repr__(self):
        return '{} (cont_type={}, id={})'.format(self.event_type, self.container_name, self.container_id)

    @property
    def event_type(self):
        """Gets the event type"""
        return self._event_type

    @property
    def container_name(self):
        """Gets the container name"""
        return self._container_name

    @property
    def container_type(self):
        """Gets the container_type (same as calling pluralize(container_name))"""
        return pluralize(self._container_name)

    @property
    def container_id(self):
        """Gets the container id"""
        return self._container_id

    @staticmethod
    def normalize_event_type(event_type):
        """Normalize an event type (e.g. from a string) to ContainerEventType"""
        if isinstance(event_type, ContainerEventType):
            return event_type
        return ContainerEventType[event_type] # pylint: disable=unsubscriptable-object

    @classmethod
    def factory(cls, event_type, container_name, container_id, **kwargs):
        """Create a new ContainerEvent for event_type

        Arguments:
            event_type (str): The event type
            container_name (str): The container name
            container_id: The container id
            **kwargs: Additional arguments to pass to the subclass constructor

        Returns:
            ContainerEvent: The subclassed container event
        """
        # Normalize event_type and container name
        event_type = ContainerEvent.normalize_event_type(event_type)
        container_name = singularize(container_name)

        subclasses = collections.deque(cls.__subclasses__())
        while subclasses:
            subclass = subclasses.popleft()
            subclasses.extend(subclass.__subclasses__())

            sc_event_type = getattr(subclass, '_event_type', None)
            if sc_event_type == event_type:
                return subclass(container_name, container_id, **kwargs)

        raise ValueError('Programmer Error: Unknown container event type: {}'.format(event_type))

class ContainerEventWithAfter(ContainerEvent):
    """Event subclass that provides lazy evaluzation of "after" container"""
    def __init__(self, container_name, container_id, storage_factory):
        super(ContainerEventWithAfter, self).__init__(container_name, container_id)
        self._storage_factory = storage_factory
        self._container_after = None

    @property
    def container_after(self):
        """ Resolves the "after" container, on-demand """
        if self._container_after is None:
            # Lazy import to prevent circular imports
            storage = self._storage_factory(self.container_type)
            self._container_after = storage.get_container(self.container_id)

        return self._container_after


class ContainerCreated(ContainerEvent):
    """Event indicating that a new container was created

    Attributes:
        cont (dict): The optional container, as it was created
    """
    _event_type = ContainerEventType.container_created

    def __init__(self, container_name, container_id, container=None):
        super(ContainerCreated, self).__init__(container_name, container_id)

        self.container = container

class ContainerUpdated(ContainerEventWithAfter):
    """Event indicating that an existing container was updated

    Attributes:
        container_before (dict): The container before it was updated
        container_after (dict): The container after it was updated (evaluated lazily)
    """
    _event_type = ContainerEventType.container_updated

    def __init__(self, container_name, container_id, container_before=None):
        from ..dao.basecontainerstorage import ContainerStorage
        super(ContainerUpdated, self).__init__(container_name, container_id, ContainerStorage.factory)

        self.container_before = container_before

class ContainerDeleted(ContainerEvent):
    """Event indicating that an existing container was deleted"""
    _event_type = ContainerEventType.container_deleted

    def __init__(self, container_name, container_id, container_before=None):
        super(ContainerDeleted, self).__init__(container_name, container_id)

        self.container_before = container_before

class ContainerFilesUpdated(ContainerEventWithAfter):
    """Event indicating files on an existing container were updated

    For example: Files were added or deleted, or 

    Attributes:
        container_before (dict): The container before it was updated
        container_after (dict): The container after it was updated (evaluated lazily)
    """
    _event_type = ContainerEventType.container_files_updated
    
    def __init__(self, container_name, container_id, container_before=None):
        from ..dao.liststorage import FileStorage
        super(ContainerFilesUpdated, self).__init__(container_name, container_id, FileStorage)

        self.container_before = container_before

def publishes_event(event_type, id_param=1, container_param=None, 
        container_before=False, require_container_before=False, id_from_result=False):
    """Decorator that wraps a storage container function and performs a notification

    Arguments:
        event_type (str): The type of event to publish (e.g. container_created)
        id_param (int): The index of the _id parameter (typically, and defaulted to 1)
        container_param (int): The index of the container parameter (for created events)
        container_before (bool): Whether or not the "before" container should be captured
        require_container_before (bool): Like container_before but raises ApiNotFoundException if not found
        id_from_result (bool): True if id should be taken from result instead
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            _self = args[0]
            _id = None if id_from_result else args[id_param]
            event_args = {}

            if container_before or require_container_before:
                cont_before = _self.get_container(_id)

                if require_container_before and not cont_before:
                    raise APINotFoundException('Could not find {} {}, resource not updated.'.format(
                        _id, _self.cont_name
                    ))

                event_args['container_before'] = cont_before

            if container_param is not None:
                event_args['container'] = args[container_param]

            result = fn(*args, **kwargs)

            # Extract container id
            if id_from_result:
                _id = result.inserted_id

            return notify_container_observers(result, _self.cont_name, event_type, _id, **event_args)

        return wrapper
    return decorator
