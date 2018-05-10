#!/bin/bash
set -e

echo "IN BOOTSTRAP ACCOUNTS"

(

# Parse input parameters...
#
# bootstrap account file
bootstrap_user_file=${1:-'/var/scitran/code/api/bootstrap.json.sample'}

# Create root user
#
BOOTSTRAP_USER_EMAIL=${2:-'bootstrap.user@flywheel.com'}
BOOTSTRAP_USER_FIRST_NAME=${3:-'bootstrapuser'}
BOOTSTRAP_USER_LAST_NAME=${4:-'bootstrapuser'}
BOOTSTRAP_USER_KEY=$(curl -k -X POST $SCITRAN_SITE_API_URL/users -d '{"_id": "'$BOOTSTRAP_USER_EMAIL'", "firstname": "'$BOOTSTRAP_USER_FIRST_NAME'", "lastname": "'$BOOTSTRAP_USER_LAST_NAME'"}' \
                  | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])")

echo "SCITRAN_CORE_API_KEY=$BOOTSTRAP_USER_KEY" > /dev.dynamic.env

# Move to API folder for relative path assumptions later on
#
cd /var/scitran/code/api

# Export PYTHONPATH for python script later on.
#
export PYTHONPATH=.


# Bootstrap Users
./bin/load_users_drone_secret.py --insecure --key "${BOOTSTRAP_USER_KEY}" "${SCITRAN_SITE_API_URL}" "${bootstrap_user_file}"


)
