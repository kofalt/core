import pytest
from prometheus_client.parser import text_string_to_metric_families

@pytest.mark.skip(reason="Metrics endpoint currently fails on nginx-unit")
def test_metrics(as_drone):
    r = as_drone.get('/metrics')
    assert r.ok
    assert len(r.text) > 0

    # Check for existence of a few unlabeled values
    expected_names = {'fw_db_version', 'uwsgi_worker_deaths'}

    for family in text_string_to_metric_families(r.text):
        if family.name in expected_names:
            expected_names.remove(family.name)

    assert len(expected_names) == 0
