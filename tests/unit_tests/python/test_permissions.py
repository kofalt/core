
from api.auth import containerauth

import pytest
from mock import patch

def test_validate_container_permission(mocker):
    with pytest.raises(ValueError):
        containerauth.validate_container_permissions([], 'bad container', 1234, 'admin')

    with patch('api.auth.containerauth.db') as mocked_db:
        #from api.auth.containerauth import validate_container_permissions

        mocked_db.sessions.find.return_value = 'Ryan is the best ever'

        # Validate the permission leves are set to the limit for the permission checked
        containerauth.validate_container_permissions([], 'sessions', 1234, 'admin')
        for args in mocked_db['sessions'].find.call_args_list[0]:
            for arg in args:
                assert arg['permissions']['$elemMatch']['$and'][1]['access']['$in'] == ['admin']


        containerauth.validate_container_permissions([], 'sessions', 1234, 'rw')
        for args in mocked_db['sessions'].find.call_args_list[1]:
            for arg in args:
                assert arg['permissions']['$elemMatch']['$and'][1]['access']['$in'] == ['admin', 'rw']

        containerauth.validate_container_permissions([], 'sessions', 1234, 'ro')
        for args in mocked_db['sessions'].find.call_args_list[2]:
            for arg in args:
                assert arg['permissions']['$elemMatch']['$and'][1]['access']['$in'] == ['admin', 'rw', 'ro']
