import collections

from ..dao import containerutil
from .. import config

class AggregationStage(object):
    """Represents a single stage of aggregation.

    Attributes:
        collection (str): The name of the database collection
        fields (list): The list of field names or tuple of (dst, src) to include in projection
        sort_key (str): The sort key for this collection
        sort_order (int): The sort order for this collection (1 for ascending or -1 for descending)
        parent_key (str): The optional alternate parent key
        unwind (bool): Whether or not to include an unwind step (default is true)
    """
    def __init__(self, collection, fields=None, sort_key='created', sort_order=1, parent_key=None, unwind=True):
        self.collection = collection
        if fields:
            self.fields = fields
        else:
            self.fields = []
        self.sort_key = sort_key
        self.sort_order = sort_order
        self.parent_key = parent_key
        self.unwind = unwind

class HierarchyAggregator(object):
    """Aggregate the data hierarchy with sorting, filtering, and projection.
        
    Attributes:
        stages (list): A list of AggregationStage in aggregation order
        db (pymongo.database.Database): The connected database instance
        filter_spec (dict): The filter specification for the first stage
    """
    def __init__(self, stages=None, db=None):
        """Create a new aggregator with the given stages
        
        Args:
            stages (list): A list of AggregationStage in aggregation order
            db (pymongo.database.Database): The connected database instance
        """
        if stages is not None:
            self.stages = stages
        else:
            self.stages = []

        if db is not None:
            self.db = db
        else:
            self.db = config.db

        self.filter_spec = {}

    def execute(self):
        """Build and execute the aggregation pipeline.
        
        Returns:
            pymongo.cursor.Cursor: A cursor to the set of aggregation results
        """
        pipeline = []
        collection = None

        sort_keys = collections.OrderedDict()
        parent = None
        parent_id = None
        carryover = {}

        for stage in self.stages:
            coll = containerutil.pluralize(stage.collection)
            coll_singular = containerutil.singularize(coll)

            if not pipeline:
                # First stage, get collection and add the match stage
                collection = self.db.get_collection(coll)
                proj_pfx = ''
                pipeline.append({'$match': self.filter_spec})
            else:
                proj_pfx = coll_singular + '.'

                parent_key = stage.parent_key if stage.parent_key else parent

                # Add lookup and unwind stage
                pipeline.append({'$lookup': {
                    'from': coll,
                    'localField': parent_id,
                    'foreignField': parent_key,
                    'as': coll_singular 
                }})

                if stage.unwind:
                    pipeline.append({'$unwind': '$' + coll_singular})

            if stage.unwind:
                # Add projection
                id_field = '_meta.{}._id'.format(coll_singular)
                label_field = '_meta.{}.label'.format(coll_singular)
                sort_field = '_meta.{}._sort_key'.format(coll_singular)
                deleted_field = '_meta.{}.deleted'.format(coll_singular)

                projection = {
                    '_id': 0,
                    id_field: '${}_id'.format(proj_pfx),
                    label_field: '${}label'.format(proj_pfx),
                    sort_field: '${}{}'.format(proj_pfx, stage.sort_key),
                    deleted_field: '${}deleted'.format(proj_pfx)
                }

                projection.update(carryover)
                carryover[id_field] = 1
                carryover[label_field] = 1
                carryover[sort_field] = 1
                carryover[deleted_field] = 1

                for src in stage.fields:
                    if isinstance(src, tuple):
                        # Destination field was specified
                        field, src = src
                    else:
                        field = '{}.{}'.format(coll_singular, src)

                    projection[field] = '${}{}'.format(proj_pfx, src)
                    carryover[field] = 1

                pipeline.append({'$project': projection})

            # Add sort key
            sort_keys[sort_field] = stage.sort_order

            parent = coll_singular
            parent_id = id_field

            # Add a filter for deleted containers
            pipeline.append({
                '$match': {
                    '_meta.subject.deleted': None,
                    '_meta.session.deleted': None,
                    '_meta.acquisition.deleted': None,
                    '_meta.analysis.deleted': None
                }
            })

        # Add sorting
        pipeline.append({'$sort': sort_keys})

        return collection.aggregate(pipeline)

