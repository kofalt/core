"""Provides description of relationships in the database.

The GRAPH variable describes the connection graph of the Flywheel hierarchy.

The top-level key is a container type. Each connection in the connection list
describes a relationship. By default, the local key is '_id', the target
collection is the name of the link, and the order is '*' (many).

For parent relationships, the order should be '1'.
"""
GRAPH = {
    "groups": {"connections": {"projects": {"foreign": "group"}, "subjects": {"foreign": "parents.group"}, "sessions": {"foreign": "parents.group"}, "acquisitions": {"foreign": "parents.group"}, "jobs": {"foreign": "parents.group"}}},
    "projects": {
        "connections": {
            "group": {"local": "group", "foreign": "_id", "collection": "groups", "order": "1"},
            "subjects": {"foreign": "project"},
            "sessions": {"foreign": "project"},
            "acquisitions": {"foreign": "parents.project"},
            "analyses": {"foreign": "parent.id"},
            "jobs": {"foreign": "parents.project"},
        }
    },
    "subjects": {
        "connections": {
            "group": {"local": "parents.group", "foreign": "_id", "collection": "groups", "order": "1"},
            "project": {"local": "project", "foreign": "_id", "collection": "projects", "order": "1"},
            "sessions": {"foreign": "subject"},
            "acquisitions": {"foreign": "parents.subject"},
            "analyses": {"foreign": "parent.id"},
            "jobs": {"foreign": "parents.subject"},
        }
    },
    "sessions": {
        "connections": {
            "group": {"local": "parents.group", "foreign": "_id", "collection": "groups", "order": "1"},
            "project": {"local": "project", "foreign": "_id", "collection": "projects", "order": "1"},
            "subject": {"local": "subject", "foreign": "_id", "collection": "subjects", "order": "1"},
            "acquisitions": {"foreign": "session"},
            "analyses": {"foreign": "parent.id"},
            "jobs": {"foreign": "parents.session"},
        }
    },
    "acquisitions": {
        "connections": {
            "group": {"local": "parents.group", "foreign": "_id", "collection": "groups", "order": "1"},
            "project": {"local": "parents.project", "foreign": "_id", "collection": "projects", "order": "1"},
            "subject": {"local": "parents.subject", "foreign": "_id", "collection": "subjects", "order": "1"},
            "session": {"local": "session", "foreign": "_id", "collection": "sessions", "order": "1"},
            "analyses": {"foreign": "parent.id"},
            "jobs": {"foreign": "parents.acquisition"},
        }
    },
    "analyses": {
        "connections": {
            "group": {"local": "parents.group", "foreign": "_id", "collection": "groups", "order": "1"},
            "project": {"local": "parents.project", "foreign": "_id", "collection": "projects", "order": "1"},
            "subject": {"local": "parents.subject", "foreign": "_id", "collection": "subjects", "order": "1"},
            "session": {"local": "parents.session", "foreign": "_id", "collection": "sessions", "order": "1"},
            "acquisition": {"local": "parents.acquisition", "foreign": "_id", "collection": "acquisitions", "order": "1"},
            "jobs": {"foreign": "parents.analyses"},
        }
    },
    "jobs": {
        "connections": {
            "group": {"local": "parents.group", "foreign": "_id", "collection": "groups", "order": "1"},
            "project": {"local": "parents.project", "foreign": "_id", "collection": "projects", "order": "1"},
            "subject": {"local": "parents.subject", "foreign": "_id", "collection": "subjects", "order": "1"},
            "session": {"local": "parents.session", "foreign": "_id", "collection": "sessions", "order": "1"},
            "acquisition": {"local": "parents.acquisition", "foreign": "_id", "collection": "acquisitions", "order": "1"},
            "analysis": {"local": "parents.analysis", "foreign": "_id", "collection": "analyses", "order": "1"},
        }
    },
}
