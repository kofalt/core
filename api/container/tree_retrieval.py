"""Provides functionality to retrieve a portion of the flywheel tree, with connections"""
import collections

import pymongo

from .graph import GRAPH
from ..dao.containerstorage import cs_factory, ContainerStorage
from ..web import errors
from .. import util


class TreeRetrieval(object):
    """This class will perform a paged tree retreival, given an input specification.

    When performing a retrieval, the top-level set of documents will be retrieved
    using the pagination specified at the endpoint, including filtering, sorting & limiting.

    For connected documents (e.g. children) a subset of pagination is supported via the
    sort, limit and filter fields. In the case of files (or inputs for analyses) filtering
    is not supported, and sorting is limited to a single, primitive field.

    It's worth noting that each connection described in the document is an additional query
    to the database - there currently is no logic to try to group all retrievals by
    collection.

    This class makes heavy use of the 'graph' submodule, which describes the
    major connections in the hierarchy.

    An example retrieval:

        {"acquisitions": {
            "fields": ["label", "timestamp", "modality", "classification"],
            "files": {
                "sort": "name:asc",
                "limit": 5,
                "join-origin": true,
                "fields": ["name", "size", "type"]
            }
        }})
    """

    MAX_LIMIT = 50

    def __init__(self, log):
        """Initialize a tree retrieval.

        Args:
            log (logger): The context log object
        """
        self.log = log

    def retrieve(self, spec, pagination, user):
        """Perform the retrieval outlined in the spec document.

        Args:
            spec (dict): The input specification
            pagination (dict): The initial pagination arguments
            user (str): The user_id if authorization is required, else None

        Returns:
            list|dict: The page that was retrieved.
        """
        # Determine first collection
        if len(spec) != 1:
            raise errors.InputValidationException("Expected exactly 1 top-level collection")

        # Create a queue of retrievals to perform
        retrievals = collections.deque()

        # Enforce maximum page limit for top-level
        if "limit" in pagination:
            pagination["limit"] = min(pagination["limit"], self.MAX_LIMIT)
        else:
            pagination["limit"] = self.MAX_LIMIT

        # Fetch using get_all_el & pagination
        collection_name, collection_spec = spec.items()[0]

        # The initial storage factory
        storage = cs_factory(collection_name)
        projection = self._get_projection(collection_name, collection_spec)

        # Retrieve all elements
        if user and collection_name in ("analyses", "jobs"):
            # Pre-flight, use project permissions to find analyses/jobs
            project_storage = cs_factory("projects")
            projects = project_storage.get_all_el(None, user, {"_id": 1})
            query = {"parents.project": {"$in": [proj["_id"] for proj in projects]}}
            response = storage.get_all_el(query, None, projection, pagination=pagination)
        else:
            response = storage.get_all_el(None, user, projection, pagination=pagination, join_subjects=False)

        results = response["results"]
        self._sort_and_limit_files(collection_spec, results)

        # Create the initial retrieval list
        self._add_connection_retrievals(retrievals, collection_name, collection_spec, results)

        while retrievals:
            # Get next join
            connection_name, connection_spec, collection_spec, nodes = retrievals.popleft()
            collection_name = connection_spec.get("collection", connection_name)
            order = connection_spec.get("order", "*")  # Order is '1' or '*'

            # Build query
            local_id_field = connection_spec.get("local", "_id")
            local_id_fn = self._extract_field_fn(local_id_field)

            foreign_id_field = connection_spec["foreign"]
            foreign_id_fn = self._extract_field_fn(foreign_id_field)

            container_map = {}
            keys = []
            for container in nodes:
                local_id = local_id_fn(container)
                keys.append(local_id)
                container_map.setdefault(local_id, []).append(container)

                # Setup default value
                if order == "*":
                    container[connection_name] = []
                else:
                    container[connection_name] = None

            # Don't fetch if keys is empty
            if keys:
                query = {foreign_id_field: {"$in": keys}}

                # Build pagination
                pagination, child_limit = self._get_pagination(collection_spec)

                # Build projection
                projection = self._get_projection(collection_name, collection_spec)
                projection[foreign_id_field] = 1

                # Do retrieval
                storage = cs_factory(collection_name)

                # Don't include permission check for jobs/analyses
                child_user = None if collection_name in ("analyses", "jobs") else user
                children = storage.get_all_el(query, child_user, projection, pagination=pagination, join_subjects=False)["results"]

                self._sort_and_limit_files(collection_spec, children)
            else:
                children = []

            # Perform join
            for child in children:
                foreign_id = foreign_id_fn(child)
                parents = container_map.get(foreign_id, [])
                for parent in parents:
                    if order == "*":
                        current = parent[connection_name]
                        if child_limit is None or len(current) < child_limit:
                            current.append(child)
                    else:
                        parent[connection_name] = child

            # Add next level of retrievals
            if children:
                self._add_connection_retrievals(retrievals, collection_name, collection_spec, children)

        return response

    def _add_connection_retrievals(self, retrievals, collection_name, collection_spec, nodes):
        """Push additional retrievals onto the retrieval queue.

        Args:
            retrievals (deque): The queue of retrievals
            collection_name (str): The plural collection name
            collection_spec (dict): The input collection specification
            nodes (list): The current set of nodes to operate on
        """
        node = GRAPH[collection_name]
        for connection_name, connection_spec in node["connections"].items():
            child_spec = collection_spec.get(connection_name)
            if child_spec is not None:
                retrievals.append((connection_name, connection_spec, child_spec, nodes))

    def _get_pagination(self, spec):
        """Create a pagination object from a container input specification.

        This form of pagination only supports filter, sort and limit.

        Args:
            spec (dict): The specification object

        Returns:
            tuple(dict, int): The pagination object and limit (or None if no limit is given)
        """
        # Light-weight subset of pagination, supports filter, sort and limit
        pagination = {}

        if "filter" in spec:
            pagination["filter"] = util.parse_pagination_filter_param(spec.pop("filter"))
        if "sort" in spec:
            pagination["sort"] = util.parse_pagination_sort_param(spec.pop("sort"))

        if "limit" in spec:
            limit = int(spec.pop("limit"))
        else:
            limit = None

        return pagination, limit

    def _get_projection(self, collection_name, collection_spec):
        """Compute a projection, given a collection name and input specification.

        Args:
            collection_name (str): The (plural) collection name
            collection_spec (dict): The collection specificiation

        Returns:
            dict: A projection document for the given collection
        """
        fields = collection_spec.pop("fields", [])

        result = {field: 1 for field in fields}
        result["_id"] = 1

        # Project files/inputs, as requested
        if "files" in collection_spec:
            result["files"] = 1

        if "inputs" in collection_spec:
            result["inputs"] = 1

        # Add FK required fields
        node = GRAPH[collection_name]
        for connection_name, connection_spec in node["connections"].items():
            child_spec = collection_spec.get(connection_name)
            if child_spec is not None:
                local_id_field = connection_spec.get("local")
                if local_id_field is not None:
                    result[local_id_field] = 1

        return result

    def _sort_and_limit_files(self, collection_spec, containers):
        """Sort and limit 'inputs' and/or 'files' on each container in a list.

        Args:
            collection_spec (dict): The input collection specification.
            containers (list): The list of containers to update
        """
        if not containers:
            return

        input_update_fn = self._sort_and_limit_files_fn("inputs", collection_spec)
        if input_update_fn:
            map(input_update_fn, containers)
            if collection_spec["inputs"].get("join-origin", False):
                ContainerStorage.join_origins(containers, "inputs")

        files_update_fn = self._sort_and_limit_files_fn("files", collection_spec)
        if files_update_fn:
            map(files_update_fn, containers)
            if collection_spec["files"].get("join-origin", False):
                ContainerStorage.join_origins(containers, "files")

    @staticmethod
    def _sort_and_limit_files_fn(key, collection_spec):
        """Create a function that will sort and limit the files (or inputs) subdocument.

        Args:
            key (str): The key - typically either 'inputs' or 'files'
            collection_spec (dict): The input collection spec which contains an 'inputs'
                or 'files' key with a set of fields and an optional sort / limit spec.

        Returns:
            function: A function that can be applied to a container to sort & limit files.
        """
        spec = collection_spec.get(key)
        if not spec:
            return None

        if spec.get("filter"):
            raise errors.InputValidationException("Cannot filter files!")

        limit = spec.get("limit")
        sort = spec.get("sort")

        if sort:
            sort = util.parse_pagination_sort_param(sort)

            if len(sort) > 1:
                raise errors.InputValidationException("Cannot sort files by more than one field")

            sort_field, order = sort[0]
            sort_reverse = order == pymongo.DESCENDING
            sort_key_fn = lambda x: x.get(sort_field)
        else:
            sort_key_fn = None
            sort_reverse = False

        fields = spec["fields"]

        # Ensure that _id is included in subdocs
        if "_id" not in fields:
            fields.append("_id")

        # Ensure origin when join-origin is True
        if spec.get("join-origin", False) and "origin" not in fields:
            fields.append("origin")

        def result_fn(cont):
            # Deleted files should already be removed
            files = cont.pop(key, [])

            # Sort
            if sort_key_fn:
                files.sort(key=sort_key_fn, reverse=sort_reverse)

            # Limit
            if limit:
                files = files[:limit]

            # Project
            result = []
            for entry in files:
                proj_entry = {}
                for field in fields:
                    if field in entry:
                        proj_entry[field] = entry[field]
                result.append(proj_entry)

            cont[key] = result

        return result_fn

    @staticmethod
    def _extract_field_fn(key):
        """Returns a function to pop the given key off a container.

        Args:
            key (str): The one or two part key to extract

        Return:
            function: A function that takes a container and pops the key
        """
        parts = key.split(".")
        if len(parts) == 1:
            if key == "_id":
                # Don't pop id field
                return lambda cont: cont.get(key)
            return lambda cont: cont.pop(key, None)

        elif len(parts) == 2:

            def pop_field(cont):
                if parts[0] not in cont:
                    return None

                child = cont[parts[0]]
                # Remove values as we extract
                result = child.pop(parts[1], None)
                if not child:
                    cont.pop(parts[0])
                return result

            return pop_field
        raise RuntimeError("Invalid key: {}".format(key))
