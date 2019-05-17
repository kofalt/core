import pytest

from api import models


def test_base_model():
    class Container(models.Base):
        def __init__(self, label, public=False, info=None):
            self._id = None
            self.label = label
            self.public = public
            self.info = info

    container = Container("Test Label", info={"my": "value"})

    assert container.label == "Test Label"
    assert container.public == False
    assert container.info == {"my": "value"}
    assert container.foo == None  # Arbitrary attribute access results in None

    container._id = "test"
    assert container.to_dict() == {"_id": "test", "label": "Test Label", "public": False, "info": {"my": "value"}}

    # Can delete any field, and add any additional fields
    del container._id
    del container.info
    container["foo"] = "bar"

    assert container.to_dict() == {"label": "Test Label", "public": False, "foo": "bar"}

    # Can get a field via square-brackets
    assert container["label"] == "Test Label"
    # Can get with default
    assert container.get("label", "blah") == "Test Label"
    assert container.get("label2", "blah") == "blah"

    with pytest.raises(KeyError):
        y = container["not_exist"]

    # Can get keys
    expected_keys = {"label", "public", "foo"}
    assert set(container.keys()) == expected_keys

    # Test In
    assert "label" in container
    assert "foo" in container
    assert "bar" not in container

    # Test length
    assert len(container) == 3

    # Test iteration
    for key in container:
        assert key in expected_keys

    for key, value in container.iteritems():
        assert key in expected_keys
        assert container[key] == value

    for key, value in container.items():
        assert key in expected_keys
        assert container[key] == value

    # Can create from a dictionary
    c2 = Container.from_dict({"label": "Test Label", "public": False, "foo": "bar"})
    assert container._id == None
    assert container.label == "Test Label"
    assert container.public == False
    assert container.info == None
    assert container.foo == "bar"  # Arbitrary attribute access results in None

    # Test equality
    c3 = Container(label=u"container3")
    assert c3.to_dict() == {"_id": None, "label": u"container3", "public": False, "info": None}

    assert container == c2
    assert container != c3
    assert c2 != c3

    # Test nested conversion
    assert container.pop("foo") == "bar"
    with pytest.raises(KeyError):
        container.pop("foo")
    assert container.pop("foo", None) == None

    # Test set default
    assert container.setdefault("children", [c2, c3]) == [c2, c3]

    # Test update
    container.update({"label": "New Label", "foo": "bar"})

    # Test direct assignment
    container.test = {"nested": c3}

    assert container.to_dict() == {"label": "New Label", "public": False, "foo": "bar", "children": [c2.to_dict(), c3.to_dict()], "test": {"nested": c3.to_dict()}}

    # Test inheritance
    class Session(Container):
        def __init__(self, label, public=False, info=None, timestamp=None):
            super(Session, self).__init__(label, public=public, info=info)
            self.timestamp = timestamp

    s1 = Session(label="session1", timestamp="yesterday")
    assert s1.to_dict() == {"_id": None, "label": "session1", "public": False, "info": None, "timestamp": "yesterday"}

    s2 = Session.from_dict(s1.to_dict())
    assert s1 == s2
