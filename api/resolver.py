"""
Resolve an ambiguous path through the data hierarchy.

The goal of the resolver is to provide a virtual graph that can be navigated using
path notation. Below is how the graph will ultimately be represented. Currently
subjects are excluded by default, and can be enabled with the feature-toggle
"Subject-Container".

Quoted strings represent literal nodes in the graph. For example, to find the gear
called dicom-mr-classifier, you would use the path: ["gears", "dicom-mr-classifier"]

+----+   +-------+   +-----+   +-------+
|Root+---+"gears"+---+Gears+---+Version|
+-+--+   +-------+   +-----+   +-------+
  |
+-+----+
|Groups|
+-+----+
  |
+-+------+
|Projects+---+
+-+------+   |
  |          |
+-+------+   |   +----------+   +--------+
|Subjects+---+---+"analyses"+---+Analyses|
+-+------+   |   +----------+   +---+----+
  |          |                      |
+-+------+   |                      |
|Sessions+---+-------+              |
+-+------+           |          +---+---+   +-----+
  |                  +----------+"files"+---+Files|
+-+----------+       |          +-------+   +-----+
|Acquisitions+-------+
+------------+
"""
import bson

from collections import deque

from .dao import containerutil
from .dao.basecontainerstorage import ContainerStorage
from .jobs import gears
from .web.errors import APINotFoundException, InputValidationException


def set_container_type(node, container_type):
    """Set container_type on node.

    This function sets node_type in addition to container_type so that
    older clients (CLI, SDK) remain compatible with a minor version mismatch.
    """
    node["container_type"] = container_type
    node["node_type"] = container_type


def apply_container_type(lst, container_type):
    """Apply container_type to each item in in the list"""
    for item in lst:
        set_container_type(item, container_type)


def raise_not_found(msg, path):
    """Raise an APINotFoundException, possibly including a suggested path"""
    # If there's a dot in the name, assume that they're trying to resolve
    # a file, and suggest using the files/ prefix
    if not path.startswith("files/") and "." in path:
        msg += "\nDid you mean files/{}?".format(path)
    raise APINotFoundException(msg)


class Node(object):
    """Base class for all nodes in the resolver tree"""

    def next(self, path_in, path_out, id_only):  # pylint: disable=W0613
        """
        Find the next node in the hierarchy that matches the next item in path_in.
        Places the found node in path_out and return the next Node in the tree.

        Args:
            path_in (deque): The remaining path elements to search in left-to-right order.
            path_out (list): The currently resolved path, in left-to-right order.
            id_only (bool): Whether to resolve just ids for path elements, or full nodes.

        Returns:
            Node: The next node in the hierarchy, or None
        """
        raise NotImplementedError()

    def get_children(self, path_out):  # pylint: disable=W0613
        """
        Get all children of the last path element.

        Args:
            path_out (list): The currently resolved path.

        Returns:
            list: A list of child elements for the last path element.
        """
        raise NotImplementedError()

    def get_parent(self, path_out):
        """Return the last element in path_out or None"""
        if path_out:
            return path_out[-1]
        return None

    def parse_criterion(self, path_in):
        """
        Parse criterion, returning true if we got an id.

        Args:
            path_in (deque): The path in, must not be empty.

        Returns:
            bool, str: A boolean value indicating whether or not we parsed an id, and the parsed value.
        """
        value = path_in.popleft()
        use_id = False

        # Check for <id:xyz> syntax
        if value.startswith("<id:") and value.endswith(">"):
            value = value[4 : len(value) - 1]
            use_id = True

        return use_id, value


class FilesNode(Node):
    """Node that manages filename resolution"""

    def next(self, path_in, path_out, id_only):
        filename = path_in.popleft()
        parent = self.get_parent(path_out)

        # Find the matching file
        for f in FilesNode.pop_files(parent):
            if str(f.get("name", "")) == filename:
                path_out.append(f)
                return None

        raise APINotFoundException("No " + filename + " file found.")

    def get_children(self, path_out):
        parent = self.get_parent(path_out)
        return FilesNode.pop_files(parent)

    @staticmethod
    def pop_files(container):
        """
        Return a consistently-ordered set of files for a given container.
        This will remove the 'files' attribute from the container.

        Args:
            container (dict): The container, or None if there is no parent.

        Returns:
            list: The list of files, or an empty list
        """
        if not container:
            return []

        files = container.pop("files", [])

        files.sort(key=lambda f: f.get("name", ""))
        apply_container_type(files, "file")

        return files


class ContainerNode(Node):
    # All lists obtained by the Resolver are sorted by the created timestamp, then the database ID as a fallback.
    # As neither property should ever change, this sort should be consistent
    sorting = [("created", 1), ("_id", 1)]

    def __init__(self, cont_name, files=True, use_id=False, analyses=True, include_subjects=False):
        self.cont_name = cont_name
        self.storage = ContainerStorage.factory(cont_name)
        # container_type is also the parent id field name
        self.container_type = containerutil.singularize(cont_name)
        self.files = files
        self.use_id = use_id
        self.analyses = analyses
        self.include_subjects = include_subjects
        self.child_name = self.storage.child_cont_name
        if self.container_type == "project" and not include_subjects:
            self.child_name = "sessions"

    def next(self, path_in, path_out, id_only):
        use_id, criterion = self.parse_criterion(path_in)
        parent = self.get_parent(path_out)
        # Peek to see if we need files for the next path element
        fetch_files = not path_in or path_in[0] == "files"

        # Setup criterion match
        query = {}
        if use_id or self.use_id:
            if self.storage.use_object_id:
                try:
                    query["_id"] = bson.ObjectId(criterion)
                except bson.errors.InvalidId as e:
                    raise InputValidationException(e.message)
            else:
                query["_id"] = criterion
        else:
            label_key = "code" if self.container_type == "subject" else "label"
            query[label_key] = criterion

        # Setup projection
        if id_only:
            proj = self.get_id_only_projection()
            if fetch_files:
                proj["files"] = 1
        else:
            proj = self.storage.get_list_projection()
            if proj and not fetch_files:
                proj["files"] = 0

        results = self.find(query, parent, proj)
        if not results:
            msg = "No {} {} found.".format(criterion, self.container_type)
            raise_not_found(msg, criterion)

        child = results[0]

        self.storage.filter_container_files(child)
        set_container_type(child, self.container_type)
        path_out.append(child)

        # Get the next node
        if path_in:
            # Files
            if fetch_files:
                path_in.popleft()
                return FilesNode()

            # Check for analyses
            if path_in[0] == "analyses" and self.analyses:
                path_in.popleft()
                return AnalysesNode()

            # Otherwise, the next node is our child container
            if self.child_name:
                return ContainerNode(self.child_name, include_subjects=self.include_subjects)

        return None

    def get_children(self, path_out):
        parent = self.get_parent(path_out)

        # Get container chilren
        if self.child_name:
            query = {}
            if parent:
                query[parent["container_type"]] = parent["_id"]

            children = ContainerNode.get_container_children(self.child_name, query)
        else:
            children = []

        # Add analyses
        if self.analyses:
            analyses_node = AnalysesNode()

            proj = analyses_node.storage.get_list_projection()
            if proj:
                proj["files"] = 0

            analyses = analyses_node.list_analyses(parent, proj=proj)
            apply_container_type(analyses, analyses_node.container_type)
            children = children + analyses

        # Add files
        return children + FilesNode.pop_files(parent)

    def find(self, query, parent, proj):
        """ Find the one child of this container that matches query """
        # Add parent to query
        if parent:
            query[parent["container_type"]] = parent["_id"]

        # We don't use the user field here because we want to return a 403 if
        # they try to resolve something they don't have access to
        return self.storage.get_all_el(query, None, proj, sort=ContainerNode.sorting, limit=1)

    def get_id_only_projection(self):
        """Return a projection that will return the minimal values required for id-only resolution."""
        label_key = "code" if self.container_type == "subject" else "label"
        return {label_key: 1, "permissions": 1, "files": 1}

    @staticmethod
    def get_container_children(cont_name, query=None):
        """Get all children of container named cont_name, using query"""
        storage = ContainerStorage.factory(cont_name)

        proj = storage.get_list_projection()
        if proj:
            proj["files"] = 0

        children = storage.get_all_el(query, None, proj, sort=ContainerNode.sorting)
        apply_container_type(children, containerutil.singularize(cont_name))

        return children


class GearsNode(Node):
    """The top level "gears" node"""

    def next(self, path_in, path_out, id_only):
        use_id, criterion = self.parse_criterion(path_in)
        if use_id:
            gear = gears.get_gear(criterion)
        else:
            gear = gears.get_latest_gear(criterion)

        if not gear:
            raise APINotFoundException("No gear {0} found.".format(criterion))

        set_container_type(gear, "gear")
        path_out.append(gear)

        return GearVersionNode()

    def get_children(self, path_out):
        results = gears.get_gears()

        for gear in results:
            set_container_type(gear, "gear")

        return results


class GearVersionNode(Node):
    def next(self, path_in, path_out, id_only):
        version = path_in.popleft()

        parent = self.get_parent(path_out)
        # Raises if not found
        gear = gears.get_gear_version(parent["gear"]["name"], version)

        set_container_type(gear, "gear")
        path_out.append(gear)

        return None

    def get_children(self, path_out):
        # Children are all gear versions with the same name, minus the parent
        # Only return children for the first gear in path_out
        if len(path_out) == 1:
            # Since results are sorted, just exclude the latest (parent) gear
            parent = path_out[-1]
            results = gears.get_all_gear_versions(parent["gear"]["name"])[1:]
        else:
            results = []

        for gear in results:
            set_container_type(gear, "gear")

        return results


class AnalysesNode(ContainerNode):
    def __init__(self):
        super(AnalysesNode, self).__init__("analyses", files=True, use_id=False, analyses=False)

    def find(self, query, parent, proj):
        return self.list_analyses(parent, query, proj, limit=1)

    def get_children(self, path_out):
        parent = self.get_parent(path_out)

        # Only children of an analyses is files
        if parent.get("container_type") == "analysis":
            return FilesNode.pop_files(parent)

        results = self.list_analyses(parent)
        apply_container_type(results, self.container_type)
        return results

    def list_analyses(self, parent, query=None, proj=None, **kwargs):
        """Get a list of all analyses that match query, using the given projection"""
        return self.storage.get_analyses(query, parent["container_type"], parent["_id"], projection=proj, sort=ContainerNode.sorting, **kwargs)


class RootNode(Node):
    """The root node of the resolver tree"""

    def __init__(self, include_subjects=False):
        self.include_subjects = include_subjects

    def next(self, path_in, path_out, id_only):
        """Get the next node in the hierarchy"""
        if path_in[0] == "gears":
            path_in.popleft()
            return GearsNode()

        return ContainerNode("groups", files=False, use_id=True, analyses=False, include_subjects=self.include_subjects)

    def get_children(self, path_out):
        """Get the children of the current node in the hierarchy"""
        return ContainerNode.get_container_children("groups")


class Resolver(object):
    """
    Given an array of human-meaningful, possibly-ambiguous strings, resolve it as a path through the hierarchy.

    Does not tolerate ambiguity at any level of the path except the final node.
    """

    def __init__(self, id_only=False, include_subjects=False):
        self.id_only = id_only
        self.include_subjects = include_subjects

    def resolve(self, path):
        if not isinstance(path, list):
            raise InputValidationException("Path must be an array of strings")

        path = deque(path)
        node = None
        next_node = RootNode(include_subjects=self.include_subjects)

        resolved_path = []
        resolved_children = []

        # Walk down the tree, building path until we get to a leaf node
        # Keeping in mind that path may be empty
        while next_node:
            node = next_node

            # Don't attempt to resolve the next node if path is empty
            if not path:
                break

            next_node = node.next(path, resolved_path, self.id_only)

        # If we haven't consumed path, then we didn't find what we were looking for
        if len(path) > 0:
            msg_path = "/".join(path)
            msg = "Could not resolve node for: {}".format(msg_path)
            raise_not_found(msg, msg_path)

        if hasattr(node, "get_children"):
            resolved_children = node.get_children(resolved_path)

        return {"path": resolved_path, "children": resolved_children}
