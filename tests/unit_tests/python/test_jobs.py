import bson
from api.jobs import job_util


def test_removing_phi_from_job_map():
    job_map = {"_id": bson.ObjectId(), "produced_metadata": {"session": {"label": "hi"}}, "config": {"inputs": {"dicom": {"base": "file", "object": {"info": {"phi": True}}}}}}
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get("produced_metadata") is None
    assert clean_job_map["config"]["inputs"]["dicom"]["object"].get("info") is None


def test_removing_phi_from_job_map_without_produced_metadata():
    job_map = {"_id": bson.ObjectId(), "config": {"inputs": {"dicom": {"base": "file", "object": {"info": {"phi": True}}}}}}
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get("produced_metadata") is None
    assert clean_job_map["config"]["inputs"]["dicom"]["object"].get("info") is None


def test_removing_phi_from_job_map_without_config():
    job_map = {"_id": bson.ObjectId(), "produced_metadata": {}}
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get("produced_metadata") is None
    assert clean_job_map.get("config") is None


def test_removing_phi_from_job_map_with_config_set_to_None():
    job_map = {"_id": bson.ObjectId(), "produced_metadata": {}, "config": None}
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get("produced_metadata") is None
    assert clean_job_map.get("config") is None
