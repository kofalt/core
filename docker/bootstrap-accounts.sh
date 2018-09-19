#!/bin/bash
set -e
set -x

echo "IN BOOTSTRAP ACCOUNTS"

(

# Parse input parameters...
#
# bootstrap account file
bootstrap_user_file=${1:-'/src/core/bootstrap.json.sample'}


# Move to API folder for relative path assumptions later on
#
cd /src/core

# Export PYTHONPATH for python script later on.
#
export PYTHONPATH=.


# Bootstrap Users
./bin/load_users_drone_secret.py --insecure --secret "${SCITRAN_CORE_DRONE_SECRET}" "${SCITRAN_SITE_API_URL}" "${bootstrap_user_file}"


)
