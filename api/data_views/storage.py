import bson
import datetime

from ..dao.basecontainerstorage import ContainerStorage
from ..dao.containerutil import container_search, singularize
from ..web.errors import APINotFoundException, APIStorageException

PARENT_CONTAINERS = ['users', 'projects', 'groups']

class DataViewStorage(ContainerStorage):
    """ContainerStorage class for Data Views"""
    def __init__(self):
        super(DataViewStorage, self).__init__('data_views', use_object_id=True)

    def get_parent(self, _id, cont=None, projection=None):
        """Get the parent for the view with _id
        Arguments:
            _id (str): The data view id
            cont (dict): The optional data view container, if available
            projection (dict): The optional projection
        Returns:
            dict: The parent container
            str: The literal string 'site' if the parent is "site"
        """
        if not cont:
            cont = self.get_container(_id)

        return self.find_parent_by_id(cont['parent'], projection=projection)

    def find_parent_by_id(self, parent_id, projection=None):
        """Find the parent container based on parent_id alone

        Arguments:
            parent_id (str): The parent id
            projection (dict): The optional projection

        Returns:
            dict: The parent container
            str: The literal string 'site' if the parent is "site"
        """
        if parent_id == 'site':
            return parent_id
        if bson.ObjectId.is_valid(parent_id):
            parent_id = bson.ObjectId(parent_id)

        # Currently we support:
        # "site", group, project, user
        results = container_search({'_id': parent_id}, projection=projection, collections=PARENT_CONTAINERS)
        if not results:
            raise APINotFoundException('Could not find parent container: {}'.format(parent_id))

        coll_name, coll_results = results[0]
        parent = coll_results[0]
        parent['cont_name'] = singularize(coll_name)
        return parent

    def get_data_views(self, parent_id, public_only = False):
        """Get all data views belonging to parent_id
        
        Arguments:
            parent_id (str): The parent id

        Returns:
            list: The list of data views belonging to parent_id
        """
        query = {
            'parent': str(parent_id)
        }

        if public_only:
            query['public'] = True

        return self.get_all_el(query, None, None)

    # pylint: disable=arguments-differ
    def create_el(self, view, parent_id, origin):
        """Create a new data view for parent_id
        
        Arguments:
            view (dict): The data view to create
            parent_id (str): The parent id
        """
        defaults = {
            '_id': bson.ObjectId(),
            'parent': str(parent_id),
            'created': datetime.datetime.utcnow(),
            'modified': datetime.datetime.utcnow()
        }
        for key in defaults:
            view.setdefault(key, defaults[key])

        # We store origin on the document
        view['origin'] = origin
        result = super(DataViewStorage, self).create_el(view, origin=origin)

        if not result.acknowledged:
            raise APIStorageException('Data view not created for container {}'.format(parent_id))

        return result



