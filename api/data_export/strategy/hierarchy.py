"""Provide hierarchy-walking based download strategy"""
import collections
import copy

import bson

from abc import abstractmethod
from ..file_filter import filtered_files
from .abstract import AbstractDownloadStrategy

from ... import config, validators
from ...web import errors
from ...dao import containerutil, containerstorage

class ContainerNode(object):
    """Represents a single node slated for retrieval"""
    def __init__(self, container_id=None, parent_id=None):
        self.container_id = container_id
        self.parent_id = parent_id

# Map a container name to a level in the hierarchy
# These are runtime values
CONTAINER_LEVELS = {
    'project': 1,
    'subject': 2,
    'session': 3,
    'acquisition': 4,
    'analysis': 5
}

class HierarchyDownloadStrategy(AbstractDownloadStrategy):
    """Abstract hierarchy-based download strategy.

    Walks each node in the hierarchy, based on an initial set of containers,
    providing context with all known parent containers retrieved.

    Calls visit_container for each container, and visit_file for each file that
    match the download criteria.
    """
    # Whether or not info fields are required
    require_info = False

    # Whether or not to include analyses
    include_analyses = True

    # Whether or not to visit non-leaf parent containers
    include_parents = False

    # The projection map for each container type,
    # no need to include info, deleted, parents or files
    projection_map = {
        'project': {'group': 1, 'label': 1, 'permissions': 1},
        'subject': {'project': 1, 'code': 1, 'permissions': 1},
        'session': {'subject': 1, 'label': 1, 'uid': 1, 'timestamp': 1, 'timezone': 1, 'permissions': 1},
        'acquisition': {'session': 1, 'label': 1, 'uid': 1, 'timestamp': 1, 'timezone': 1, 'permissions': 1},
        'analysis': {'parent': 1, 'label': 1, 'inputs': 1, 'uid': 1, 'timestamp': 1},
    }

    def __init__(self, log, params):
        super(HierarchyDownloadStrategy, self).__init__(log, params)

        # Create an empty set of nodes to visit for parent retrieval
        self._parent_visit_tree = self._create_visit_tree([])

        # The set of all retrieved containers by id
        self.container_id_map = {}

        # Stores each fetched container for later traversal
        self.visit_nodes = []

        # Store a set of IDs of containers that have file leaf nodes
        self.populated_nodes = set()

        # Store collection id, if provided
        self.collection_id = params.get('collection')

    def validate_spec(self, spec, summary):
        """Validate the input specification for a download.

        Args:
            spec (dict): The input specification for this download

        Raises:
            InputValidationException: If the spec is invalid
        """
        if summary:
            # Require a list
            if not isinstance(spec, list):
                raise errors.InputValidationException('Expected node list')

            for node in spec:
                # Verify that we can support downloading this level (look at projection_map)
                level = node.get('level')
                if level not in self.projection_map:
                    raise errors.InputValidationException(
                        '{} is not a recognized level'.format(level))
        else:
            validators.validate_data(spec, 'download.json', 'input', 'POST')

    def identify_targets(self, spec, uid, summary):
        # Walk through the visit_tree, top down
        # Only resolve parents if we're NOT producing a summary
        base_query = {'deleted': {'$exists': False}}
        if uid:
            base_query['permissions._id'] = uid

        filters = spec.get('filters')

        # Two stages of retrieval:
        # First stage is retrieve every specified node and its children
        visit_tree = self._create_visit_tree(spec.get('nodes', []))
        self._retrieve_nodes(base_query, visit_tree, summary)

        # Second stage is to retrieve any parents that have not been resolved
        # This is only required if producing actual paths for the download
        self._retrieve_nodes(base_query, self._parent_visit_tree, summary, parents=True)

        # Sort visit nodes by container level, descending
        # (i.e. visit acquisitions first)
        self.visit_nodes.sort(key=lambda node: node[0])

        # Final pass is visiting each container and file
        while self.visit_nodes:
            _, container_type, container = self.visit_nodes.pop()
            container_id = container['_id']

            if summary and container_type != 'analysis':
                parents = {}
            else:
                parents = self._resolve_parents(container_type, container)

            if container_type == 'analysis' and uid:
                parent = parents.get(container['parent']['type'])
                if not parent:
                    # if the parent was not found with the right permissions, user doesn't have access to the node
                    continue

            # Determine if there are any files that need to be visited
            files = filtered_files(container, filters)

            # Don't visit the container if no files matched anywhere in the down-tree
            if not files and not container_id in self.populated_nodes:
                continue

            # Mark all parents as having leaf nodes
            for _, parent in parents.items():
                if parent is not None:
                    self.populated_nodes.add(parent['_id'])

            for target in self.visit_container(parents, container_type, container, summary):
                yield target

            # Add this container to the parents and visit each file
            for file_group, file_entry in files:
                for target in self.visit_file(parents, container_type, file_group,
                        file_entry, summary):
                    yield target

    def visit_container(self, parents, container_type, container, summary):  # pylint: disable=unused-argument
        """Visit the given container, generating DownloadTargets.

        Default implementation is a no-op. If this is a summary request, then
        the destination path is not required.

        Args:
            parents (dict): The dictionary of parents for this container
            container_type (str): The singular container type
            container (dict): The container object itself
            summary (bool): Whether this is a summary request

        Returns:
            list(DownloadTarget): Any download targets to include
        """
        return []

    @abstractmethod
    def visit_file(self, parents, parent_type, file_group, file_entry, summary):
        """Visit the given file, generating DownloadTargets.

        If this is a summary request, then the destination path is not required.

        Args:
            parents (dict): The dictionary of parents of this file
            parent_type (str): The type of the parent container
            file_group (str): The file group either 'input' or 'output'
            file_entry (dict): The file entry object
            summary (bool): Whether this is a summary request

        Returns:
            list(DownloadTarget): Any download targets to include
        """

    def _get_projection(self, container_type, include_files=True):
        """Get the projection for the given container type

        Args:
            container_type (str): The type of container
            include_files (bool): Whether or not to include files in the projection

        Returns:
            dict: The projection for the given container type
        """
        result = self.projection_map.get(container_type)
        if result:
            if include_files:
                result['files'] = 1
            if self.require_info:
                result['info'] = 1
            result['parents'] = 1
            result['modified'] = 1
        return result

    def _create_visit_tree(self, nodes):
        """Creates the initial visitation tree, an ordered dictionary of containers to retrieve"""
        result = collections.OrderedDict([
            ('project', collections.deque()),
            ('subject', collections.deque()),
            ('session', collections.deque()),
            ('acquisition', collections.deque()),
            ('analysis', collections.deque()),
        ])

        for node in nodes:
            container_type = node['level']
            container_id = bson.ObjectId(node['_id'])
            result[container_type].append(ContainerNode(container_id=container_id))

        return result

    def _retrieve_nodes(self, base_query, visit_tree, summary, parents=False):
        """Retrieve nodes of container_type, based on _id or parent id.

        Args:
            base_query (dict): The base query for retrieval (Includes authorization)
            visit_tree (dict): The tree to visit
            parents (bool): Whether we're fetching children (False) or parents (True)
        """
        items = list(visit_tree.items())
        if parents:
            items.reverse()

        for container_type, nodes in items:
            if not nodes:
                continue

            # container level
            container_level = CONTAINER_LEVELS[container_type]

            # Get storage container
            storage = containerstorage.cs_factory(container_type)
            child_container_type = storage.child_cont_name
            parent_container_type = storage.parent_cont_name

            parent_keys = set()
            ids = set()

            # Note: We're not explicitly retrieving groups anywhere,
            # so we can safely assume ObjectId for ids
            for node in nodes:
                if node.parent_id is not None:
                    parent_keys.add(bson.ObjectId(node.parent_id))
                else:
                    ids.add(bson.ObjectId(node.container_id))

            query = copy.copy(base_query)
            query['$or'] = []

            # Special case for acquisitions that belong to collections
            if container_type == 'acquisition' and self.collection_id:
                query['collections'] = bson.ObjectId(self.collection_id)

            if container_type == 'analysis':
                # Use parent permissions instead
                query.pop('permissions._id', None)

            if not ids and not parent_keys:
                continue

            collection_name = containerutil.pluralize(container_type)
            parent_collection = containerutil.PARENT_FROM_CHILD.get(collection_name)
            parent_container_type = containerutil.singularize(parent_collection) if parent_collection else None

            if ids:
                query['$or'].append({'_id': {'$in': list(ids)}})

            if parent_keys:
                if parent_container_type:
                    query['$or'].append({parent_container_type: {'$in': list(parent_keys)}})
                elif container_type == 'analysis':
                    query['$or'].append({'parent.id': {'$in': list(parent_keys)}})

            # Construct the projection
            projection = self._get_projection(container_type)

            # Retrieve containers, and put them in the container map
            for container in config.db[collection_name].find(query, projection):
                container_id = container['_id']
                # Add to ID map
                self.container_id_map[container_id] = container

                # Add parent retrieval
                if container_type == 'analysis':
                    # Always retrieve analysis parents (for summary or permissions check)
                    parent_id = container['parent']['id']
                    if parent_id not in self.container_id_map:
                        parent_type = container['parent']['type']
                        self._parent_visit_tree[parent_type].append(ContainerNode(container_id=parent_id))
                elif not summary and parent_container_type != 'group':
                    parent_id = container[parent_container_type]
                    if parent_id not in self.container_id_map:
                        self._parent_visit_tree[parent_container_type].append(ContainerNode(container_id=parent_id))

                # Add any additional retrievals
                if not parents:
                    if child_container_type:
                        visit_tree[child_container_type].append(ContainerNode(parent_id=container_id))
                    if self.include_analyses and container_type != 'analysis':
                        visit_tree['analysis'].append(ContainerNode(parent_id=container_id))

                # Add to the list of nodes to visit
                if not parents or self.include_parents:
                    self.visit_nodes.append((container_level, container_type, container))

    def _resolve_parents(self, container_type, container):
        """Resolve parent references for the given container

        Args:
            container_type (str): The container type
            container (dict): The container to resolve

        Returns:
            dict: The map of parent containers
        """
        result = {container_type: container}
        for parent_type, parent_id in container.get('parents', {}).items():
            if parent_type == 'group':
                result[parent_type] = {'_id': parent_id, 'label': parent_id}
            else:
                result[parent_type] = self.container_id_map.get(parent_id)
        return result
