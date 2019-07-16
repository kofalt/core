import bson
import pytest

from mock import patch, Mock
from flywheel_common.providers import ProviderClass

from api.web import errors
from api.site import models, mappers, multiproject


@patch('api.site.multiproject.multiproject_picker.mappers.SiteSettings')
@patch('api.site.multiproject.multiproject_picker.containerstorage.cs_factory')
def test_multiproject_get_provider_id_for_container(mock_cs_factory, MockSiteSettingsCls):
    cls = ProviderClass.compute

    site_provider_id = bson.ObjectId()
    group_provider_id = bson.ObjectId()
    project_provider_id = bson.ObjectId()

    container = {
        '_id': 'test',
        'parents': {
            'group': bson.ObjectId(),
            'project': bson.ObjectId()
        }
    }

    # Mock site settings & container storage
    MockSiteSettings = Mock()
    MockSiteSettingsCls.return_value = MockSiteSettings
    MockContainerStorage = Mock()
    mock_cs_factory.return_value = MockContainerStorage

    picker = multiproject.create_provider_picker(True)

    # == No providers configured ==
    MockSiteSettings.get.return_value = None
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    is_site, provider_id = picker.get_provider_id_for_container(container, cls)
    assert is_site == False
    assert provider_id is None

    # == Site only ==
    MockSiteSettings.get.return_value = models.SiteSettings(center_gears=[], providers={'compute': site_provider_id})
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    is_site, provider_id = picker.get_provider_id_for_container(container, cls)
    assert is_site == True
    assert provider_id == site_provider_id

    # == Group ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group', 'providers': {'compute': group_provider_id}}
    )
    is_site, provider_id = picker.get_provider_id_for_container(container, cls)
    assert is_site == False
    assert provider_id == group_provider_id

    # == Project ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project', 'providers': {'compute': project_provider_id}},
        {'_id': 'group', 'providers': {'compute': group_provider_id}}
    )
    is_site, provider_id = picker.get_provider_id_for_container(container, cls)
    assert is_site == False
    assert provider_id == project_provider_id


@patch('api.site.multiproject.multiproject_picker.mappers.SiteSettings')
@patch('api.site.multiproject.multiproject_picker.containerstorage.cs_factory')
def test_multiproject_get_compute_provider_id_for_job(mock_cs_factory, MockSiteSettingsCls):
    cls = ProviderClass.compute

    site_provider_id = bson.ObjectId()
    group_provider_id = bson.ObjectId()

    gear = {'gear': {'name': 'demo-gear'}}
    destination = {
        '_id': 'test',
        'parents': {
            'group': bson.ObjectId(),
            'project': bson.ObjectId()
        }
    }
    inputs = [{}, {
        'origin': {'type': 'device'}
    }]

    # Mock site settings & container storage
    MockSiteSettings = Mock()
    MockSiteSettingsCls.return_value = MockSiteSettings
    MockContainerStorage = Mock()
    mock_cs_factory.return_value = MockContainerStorage

    picker = multiproject.create_provider_picker(True)

    MockSiteSettings.get.return_value = None
    # == Invalid gear doc ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    with pytest.raises(errors.APIValidationException):
        picker.get_compute_provider_id_for_job({}, destination, [])

    # == Nothing configured ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, []) == None

    MockSiteSettings.get.return_value = models.SiteSettings(center_gears=None, providers={'compute': site_provider_id})
    # == Non-Center Gear, No Device, No Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, []) == None

    # == Non-Center Gear, With Device, No Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, inputs) == None

    # == Non-Center Gear, No Device, With Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group', 'providers':{'compute': group_provider_id}}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, []) == group_provider_id

    # == Non-Center Gear, With Device, With Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group', 'providers':{'compute': group_provider_id}}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, inputs) == group_provider_id

    MockSiteSettings.get.return_value = models.SiteSettings(center_gears=['demo-gear'], providers={'compute': site_provider_id})
    # == Center Gear, No Device, No Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, []) == None

    # == Center Gear, With Device, No Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group'}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, inputs) == site_provider_id

    # == Center Gear, No Device, With Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group', 'providers':{'compute': group_provider_id}}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, []) == group_provider_id

    # == Center Gear, With Device, With Group Provider ==
    MockContainerStorage.get_el.side_effect = (
        {'_id': 'project'},
        {'_id': 'group', 'providers':{'compute': group_provider_id}}
    )
    assert picker.get_compute_provider_id_for_job(gear, destination, inputs) == site_provider_id

@patch('api.site.multiproject.fixed_picker.mappers.SiteSettings')
def test_fixed_provider_picker(MockSiteSettingsCls):
    site_provider_id = bson.ObjectId()

    container = {
        '_id': 'test',
        'parents': {
            'group': bson.ObjectId(),
            'project': bson.ObjectId()
        }
    }

    # Mock site settings & container storage
    MockSiteSettings = Mock()
    MockSiteSettingsCls.return_value = MockSiteSettings

    picker = multiproject.create_provider_picker(False)

    # == No providers configured ==
    MockSiteSettings.get.return_value = None

    is_site, provider_id = picker.get_provider_id_for_container(container, 'compute')
    assert is_site == False
    assert provider_id is None

    assert picker.get_compute_provider_id_for_job({}, {}, []) == None

    # == Default provider configured ==
    MockSiteSettings.get.return_value = models.SiteSettings(center_gears=None, providers={'compute': site_provider_id})
    is_site, provider_id = picker.get_provider_id_for_container(container, 'compute')
    assert is_site == True
    assert provider_id == site_provider_id

    assert picker.get_compute_provider_id_for_job({}, {}, []) == site_provider_id
