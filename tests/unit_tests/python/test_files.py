# coding=utf-8

import bson
import pytest
import mock
from api import files
from api.dao import liststorage


def test_extension():
    assert files.guess_type_from_filename("example.pdf") == "pdf"


def test_multi_extension():
    assert files.guess_type_from_filename("example.zip") == "archive"
    assert files.guess_type_from_filename("example.gephysio.zip") == "gephysio"


def test_nifti():
    assert files.guess_type_from_filename("example.nii") == "nifti"
    assert files.guess_type_from_filename("example.nii.gz") == "nifti"
    assert files.guess_type_from_filename("example.nii.x.gz") == None


def test_qa():
    assert files.guess_type_from_filename("example.png") == "image"
    assert files.guess_type_from_filename("example.qa.png") == "qa"
    assert files.guess_type_from_filename("example.qa") == None
    assert files.guess_type_from_filename("example.qa.png.unknown") == None


def test_tabular_data():
    assert files.guess_type_from_filename("example.csv") == "tabular data"
    assert files.guess_type_from_filename("example.csv.gz") == "tabular data"
    assert files.guess_type_from_filename("example.tsv") == "tabular data"
    assert files.guess_type_from_filename("example.tsv.gz") == "tabular data"


def test_unknown():
    assert files.guess_type_from_filename("example.unknown") == None


def test_eeg():
    assert files.guess_type_from_filename("example.eeg.zip") == "eeg"
    assert files.guess_type_from_filename("example.eeg") == "eeg data"
    assert files.guess_type_from_filename("example.vmrk") == "eeg marker"
    assert files.guess_type_from_filename("example.vhdr") == "eeg header"


def test_ParaVision():
    assert files.guess_type_from_filename("1.pv5.zip") == "ParaVision"
    assert files.guess_type_from_filename("1.pv6.zip") == "ParaVision"


def test_delet_file(api_db):
    filename = u"åß∂.csv"
    result = api_db.acquisitions.insert_one({"_id": bson.ObjectId(), "label": "AcquisitionLabel", "files": [{"name": filename, "origin": {"type": "user", "id": "me@email.com"}}], "session": bson.ObjectId()})
    acquisition_id = result.inserted_id

    storage = liststorage.FileStorage("acquisitions")
    storage.dbc = api_db.acquisitions

    with mock.patch("api.dao.liststorage.ListStorage._update_session_compliance"):
        storage._delete_el(acquisition_id, {"name": filename.encode("utf-8")})

    acquisition = api_db.acquisitions.find_one({"_id": acquisition_id})
    assert filename not in [f["name"] for f in acquisition.get("files", []) if f.get("deleted") is None]

    # Cleanup
    api_db.acquisitions.delete_one({"_id": acquisition_id})
