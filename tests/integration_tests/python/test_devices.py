import datetime

import bson


def test_devices(as_public, as_user, as_admin, as_drone, api_db):
    # try to get all devices w/o logging in
    r = as_public.get('/devices')
    assert r.status_code == 403

    # make sure at least one device request hits core before proceeding
    # (so that the device gets an entry in the collection even if running device tests only)
    r = as_drone.get('/groups')
    assert r.ok

    # get all devices
    r = as_user.get('/devices?join_keys=true')
    assert r.ok

    # bw-comp: verify test bootstrapper exists and has uid
    assert r.json()
    drone = r.json()[0]
    drone_id = drone['_id']

    # bw-comp: verify test bootstrapper has api key after first get
    assert as_admin.get('/devices/' + drone_id).ok
    assert api_db.apikeys.count({'origin.id': bson.ObjectId(drone_id), 'type': 'device'}) == 1

    # verify users don't have access to device keys, but admins do
    assert 'key' not in drone
    r = as_admin.get('/devices?join_keys=true')
    assert r.ok
    assert 'key' in r.json()[0]

    # try to get devices w/o logging in
    r = as_public.get('/devices/' + drone_id)
    assert r.status_code == 403

    # try to get non-existent device
    r = as_user.get('/devices/000000000000000000000000')
    assert r.status_code == 404

    # get device
    r = as_user.get('/devices/' + drone_id)
    assert r.ok

    # bw-comp: verify devices using secret have type instead of method
    drone = r.json()
    assert 'type' in drone
    assert 'method' not in drone

    # verify users don't have access to device keys, but admins do
    assert 'key' not in drone
    r = as_admin.get('/devices/' + drone_id)
    assert r.ok
    assert 'key' in r.json()

    # try to get device self as user
    r = as_admin.get('/devices/self')
    assert r.status_code == 403

    # get device self - verify that as_drone is the bootstrapper
    r = as_drone.get('/devices/self')
    assert r.ok
    device = r.json()
    assert device['_id'] == drone_id
    assert device['type'] == as_drone.headers['X-SciTran-Method']
    assert device['name'] == as_drone.headers['X-SciTran-Name']
    assert 'key' in device  # devices can also access their own key

    # try to do device check-in as user
    r = as_user.put('/devices/self')
    assert r.status_code == 403

    # try to do device check-in as admin
    r = as_user.put('/devices/self')
    assert r.status_code == 403

    # do empty device check-in (implicit last_seen update)
    r = as_drone.put('/devices/self')
    assert r.ok

    # verify last_seen was updated
    r = as_user.get('/devices/' + drone_id)
    assert r.ok
    drone_ = r.json()
    assert drone_['last_seen'] > drone['last_seen']
    del drone['last_seen']
    del drone_['last_seen']
    assert drone_ == drone

    # try to get device statuses w/o logging in
    r = as_public.get('/devices/status')
    assert r.status_code == 403

    # get device statuses
    r = as_user.get('/devices/status')
    assert r.ok
    assert drone_id in r.json()

    # try to create device w/o site admin
    r = as_user.post('/devices')
    assert r.status_code == 403

    # create device w/o root
    r = as_admin.post('/devices', json={'type': 'test'})
    assert r.ok
    device_id = r.json()['_id']
    assert api_db.apikeys.count({'origin.id': bson.ObjectId(device_id), 'type': 'device'}) == 1
    r = as_admin.get('/devices/' + device_id)
    assert r.ok
    device_key = r.json()['key']

    # no check-in interval or last_seen not set => unknown
    assert as_user.get('/devices/status').json()[device_id]['status'] == 'unknown'

    # update device - self-set check-in interval (also implicitly updates last_seen)
    as_device = as_public
    as_device.headers.update({'Authorization': 'scitran-user {}'.format(device_key)})
    r = as_device.put('/devices/self', json={'interval': 60})
    assert r.ok

    # check-in interval set + last_seen new => ok
    assert as_user.get('/devices/status').json()[device_id]['status'] == 'ok'

    # check-in interval set + last_seen old => missing
    api_db.devices.update({'_id': bson.ObjectId(device_id)},
        {'$set': {'last_seen': datetime.datetime.now() - datetime.timedelta(seconds=61)}})
    assert as_user.get('/devices/status').json()[device_id]['status'] == 'missing'

    # has errors => error
    r = as_device.put('/devices/self', json={'errors': ['does. not. compute.']})
    assert r.ok
    assert as_user.get('/devices/status').json()[device_id]['status'] == 'error'

    # delete device
    r = as_admin.delete('/devices/' + device_id)
    assert r.ok

    r = as_user.get('/devices/' + device_id)
    assert r.status_code == 404


def test_device_logging(as_drone, as_root):

    r = as_root.get('/devices/logging/ca.pem')
    assert r.status_code == 403

    r = as_drone.get('/devices/logging/logger_key.pem')
    assert r.status_code == 404

    r = as_drone.get('/devices/logging/ca.pem')
    assert r.status_code == 200

    r = as_drone.get('/devices/logging/remote_config')
    assert r.status_code == 200


def test_device_key_management(as_public, as_user, as_admin, api_db):

    # create device
    r = as_admin.post('/devices', json={'type': 'test'})
    assert r.ok
    device_id = r.json()['_id']
    r = as_admin.get('/devices/' + device_id)
    assert r.ok
    device_key = r.json()['key']

    # public and users cannot disable devices
    r = as_public.put('/devices/' + device_id, json={'disabled': True})
    assert r.status_code == 403
    r = as_user.put('/devices/' + device_id, json={'disabled': True})
    assert r.status_code == 403

    # disabling an unknown device results in not found
    r = as_admin.put('/devices/unknowndevice', json={'disabled': True})
    assert r.status_code == 404

    # disable device
    r = as_admin.put('/devices/' + device_id, json={'disabled': True})
    assert r.ok
    assert api_db.apikeys.count({'origin.id': bson.ObjectId(device_id), 'type': 'device'}) == 0

    # disabled device key is not regenerated
    r = as_admin.get('/devices/' + device_id)
    assert r.ok
    assert r.json()['disabled'] is True
    assert 'key' not in r.json()

    # disabled device key is not accepted
    as_device = as_public
    as_device.headers.update({'Authorization': 'scitran-user {}'.format(device_key)})
    r = as_device.put('/devices/self', json={'interval': 60})
    assert r.status_code == 401

    # reenable device
    r = as_admin.put('/devices/' + device_id, json={'disabled': False})
    assert r.ok
    r = as_admin.get('/devices/' + device_id)
    assert r.ok
    assert r.json()['disabled'] is False
    device_key_enabled = r.json()['key']
    assert device_key_enabled != device_key

    # public and users cannot regenerate device keys
    r = as_public.post('/devices/' + device_id + '/key')
    assert r.status_code == 401
    r = as_user.post('/devices/' + device_id + '/key')
    assert r.status_code == 403

    # regenerating the key of an unknown device results in not found
    r = as_admin.post('/devices/unknowndevice/key')
    assert r.status_code == 404

    # regenerate key
    r = as_admin.post('/devices/' + device_id + '/key')
    assert r.ok
    device_key_regen = r.json()['key']
    assert device_key_regen not in (device_key_enabled, device_key)

    # regenerated key is accepted
    as_device = as_public
    as_device.headers.update({'Authorization': 'scitran-user {}'.format(device_key_regen)})
    r = as_device.put('/devices/self', json={'interval': 60})
    assert r.ok

    # delete device
    r = as_admin.delete('/devices/' + device_id)
    assert r.ok
