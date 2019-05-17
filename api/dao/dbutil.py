import collections
import random
import time

import pymongo

from ..web.errors import APIStorageException


def try_replace_one(db, coll_name, query, update, upsert=False):
    """
    Mongo does not see replace w/ upsert as an atomic action:
    https://jira.mongodb.org/browse/SERVER-14322

    This function will try a replace_one operation, returning the result and if the operation succeeded.
    """

    try:
        result = db[coll_name].replace_one(query, update, upsert=upsert)
    except pymongo.errors.DuplicateKeyError:
        return result, False
    else:
        return result, True


def fault_tolerant_replace_one(db, coll_name, query, update, upsert=False):
    """
    Like try_replace_one, but will retry several times, waiting a random short duration each time.

    Raises an APIStorageException if the retry loop gives up.
    """

    attempts = 0
    while attempts < 10:
        attempts += 1

        result, success = try_replace_one(db, coll_name, query, update, upsert)

        if success:
            return result
        else:
            time.sleep(random.uniform(0.01, 0.05))

    raise APIStorageException("Unable to replace object.")


def try_update_one(db, coll_name, query, update, upsert=False):
    """
    Mongo does not see update w/ upsert as an atomic action:
    https://jira.mongodb.org/browse/SERVER-14322
    This function will try an update_one operation, returning the result and if the operation succeeded.
    """
    try:
        result = db[coll_name].update_one(query, update, upsert=upsert)
    except pymongo.errors.DuplicateKeyError:
        return None, False
    else:
        return result, True


class PaginationError(Exception):
    pass


def paginate_find(collection, find_kwargs, pagination):
    """Return paginated `db.coll.find()` results.

    Raises PaginationError if the query is incompatible with the pagination:
     * `sort` in find_kwargs and `after_id` in pagination
    """
    if pagination:
        if "after_id" in pagination:
            if find_kwargs.get("sort"):
                raise PaginationError('pagination "after_id" does not support sorting')
            if pagination["after_id"]:
                pagination.setdefault("filter", {})["_id"] = {"$gt": pagination["after_id"]}
            pagination["sort"] = [("_id", pymongo.ASCENDING)]

        if "filter" in pagination:
            filter_ = find_kwargs.get("filter", {})
            filter_.update(pagination["filter"])
            find_kwargs["filter"] = filter_

        if "sort" in pagination:
            sort = find_kwargs.get("sort", [])
            if isinstance(sort, basestring):
                sort = [(sort, pymongo.ASCENDING)]
            sort.extend(pagination["sort"])
            find_kwargs["sort"] = sort

        if "skip" in pagination:
            find_kwargs["skip"] = pagination["skip"]

        if "limit" in pagination:
            find_kwargs["limit"] = pagination["limit"]

    results = collection.find(**find_kwargs)
    page = {"total": results.count(), "results": list(results)}  # count ignores limit and skip by default
    return page


def paginate_pipe(collection, pipeline, pagination):
    """Return paginated `db.coll.aggregate()` results.

    Raises PaginationError if the query is incompatible with the pagination:
     * any pipeline stage is `$sort` and `after_id` in pagination
     * pagination skip used without limit
    """
    if pagination:
        if "after_id" in pagination:
            if any("$sort" in stage for stage in pipeline):
                raise PaginationError('pagination "after_id" does not support sorting')
            pagination["filter"] = {"_id": {"$gt": pagination["after_id"]}}
            pagination["sort"] = [("_id", pymongo.ASCENDING)]

        if "pipe_key" in pagination:
            pipe_key = pagination.pop("pipe_key")
            for key in pagination.get("filter", {}).keys():
                pagination["filter"][pipe_key(key)] = pagination["filter"].pop(key)
            for i, key_order in enumerate(pagination.get("sort", [])):
                key, order = key_order
                pagination["sort"][i] = (pipe_key(key), order)

        if "filter" in pagination:
            pipeline.append({"$match": pagination["filter"]})

        if "sort" in pagination:
            pipeline.append({"$sort": collections.OrderedDict(pagination["sort"])})

    pipeline.append({"$group": {"_id": None, "total": {"$sum": 1}, "results": {"$push": "$$ROOT"}}})

    if pagination:
        slice_args = None
        if "skip" in pagination and "limit" in pagination:
            slice_args = [pagination["skip"], pagination["limit"]]
        elif "limit" in pagination:
            slice_args = [pagination["limit"]]
        elif "skip" in pagination:
            raise PaginationError('pagination "skip" without "limit" is not supported for pipelines')
        if slice_args:
            pipeline.append({"$project": {"total": 1, "results": {"$slice": ["$results"] + slice_args}}})

    page = next(collection.aggregate(pipeline), {"total": 0, "results": []})
    return page
