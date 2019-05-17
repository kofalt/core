import json
import re
import string

import pytest

from api.master_subject_code.code_generator import generate_code
from api.dao.containerutil import verify_master_subject_code
from api.web.errors import InputValidationException


def test_master_subject_code_handler(as_admin, mocker, api_db):
    # if the generated subject code already exists,
    # it will try to generate new ones for 5 seconds,
    # but after that it gives up (Birth day problem)
    # In this case we can increase the length of the code
    mock_gen_code = mocker.patch("api.master_subject_code.handlers.master_subject_code_handler.code_generator.generate_code")
    mock_gen_code.return_value = "fw-BCD123"
    mocker.patch("api.master_subject_code.handlers.master_subject_code_handler.RETRY_CODE_GENERATION_TILL", 0)

    resp = as_admin.post("/subjects/master-code", json={"use_patient_id": True, "patient_id": "MRN-ABC123"})
    assert resp.status_code == 200
    assert resp.json["code"] == mock_gen_code.return_value

    resp = as_admin.post("/subjects/master-code", json={"use_patient_id": True, "patient_id": "MRN-ABC567"})
    assert resp.status_code == 409

    # can configure subject code size and prefix
    def mock_get_item(outer, inner):
        _config = {"master_subject_code": {"size": "10", "prefix": "my", "chars": "abcd1234"}}
        return _config[outer][inner]

    mocker.patch("api.master_subject_code.handlers.master_subject_code_handler.config.get_item", new=mock_get_item)

    as_admin.post("/subjects/master-code", json={"use_patient_id": True, "patient_id": "MRN-ABC567"})
    mock_gen_code.assert_called_with(length=10, prefix="my", allowed_chars="abcd1234")

    # clean up
    api_db.master_subject_codes.delete_one({"_id": mock_gen_code.return_value})


def test_generate_master_subject_code():
    code = generate_code()
    pattern = re.compile("^[0-9A-Z]{6}$")
    assert bool(pattern.match(code))

    code = generate_code(length=10, allowed_chars=string.ascii_uppercase + string.ascii_lowercase)
    pattern = re.compile("^[a-zA-Z]{10}$")
    assert bool(pattern.match(code))

    code = generate_code(length=10, prefix="my")
    pattern = re.compile("^my-[0-9A-Z]{10}$")
    assert bool(pattern.match(code))


def test_verify_master_subject_code(mocker, as_user):
    def mock_get_item(outer, inner):
        dumped_config = json.dumps({"url": "http://localhost:8080/api/subjects/master-code", "headers": dict(as_user.headers)})
        _config = {"master_subject_code": {"verify_config": dumped_config}}
        return _config[outer][inner]

    mocker.patch("api.dao.containerutil.config.get_item", new=mock_get_item)
    mocked_requests = mocker.patch("requests.get")

    verify_master_subject_code({"master_code": "CODE"})

    mocked_requests.assert_called_with("http://localhost:8080/api/subjects/master-code/CODE", headers=as_user.headers)
    # raise InputValidaiton exception if the reponse was falsy
    mocked_requests.return_value.ok = False

    with pytest.raises(InputValidationException):
        verify_master_subject_code({"master_code": "CODE"})
