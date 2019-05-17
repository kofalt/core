from prometheus_client.parser import text_string_to_metric_families


def test_metrics(as_drone, set_env, ensure_version_singleton):
    r = as_drone.get("/metrics?force_collect=True")
    assert r.ok
    assert len(r.text) > 0

    # Check for existence of a few unlabeled values
    expected_names = {"fw_core_collect_metrics_time_seconds", "fw_core_db_version", "fw_core_flywheel_version"}

    for family in text_string_to_metric_families(r.text):
        if family.name in expected_names:
            expected_names.remove(family.name)

    assert len(expected_names) == 0
