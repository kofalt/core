def test_auth_status(as_public, as_user, as_admin, as_root, as_drone):
    # public should return 403
    r = as_public.get("/auth/status")
    assert r.status_code == 403

    r = as_user.get("/auth/status")
    assert r.ok
    result = r.json()
    assert result["origin"]["type"] == "user"
    assert not result["user_is_admin"]
    assert not result["is_device"]

    r = as_admin.get("/auth/status")
    assert r.ok
    result = r.json()
    assert result["origin"]["type"] == "user"
    assert result["user_is_admin"]
    assert not result["is_device"]

    r = as_root.get("/auth/status")
    assert r.ok
    result = r.json()
    assert result["origin"]["type"] == "user"
    assert result["user_is_admin"]
    assert not result["is_device"]

    r = as_drone.get("/auth/status")
    assert r.ok
    result = r.json()
    assert result["origin"]["type"] == "device"
    assert result["user_is_admin"]
    assert result["is_device"]

    # create device
    r = as_root.post("/devices", json={"type": "test"})
    assert r.ok
    device_id = r.json()["_id"]
    try:
        # Get device key
        r = as_admin.get("/devices/" + device_id)
        assert r.ok
        device_key = r.json()["key"]

        # Verify status as device key
        as_device = as_public
        as_device.headers.update({"Authorization": "scitran-user {}".format(device_key)})
        r = as_device.get("/auth/status")
        assert r.ok
        result = r.json()
        assert result["origin"]["type"] == "device"
        assert result["user_is_admin"]
        assert result["is_device"]
    finally:
        # delete device
        r = as_root.delete("/devices/" + device_id)
        assert r.ok
