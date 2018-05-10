#!/bin/bash
set -e
set -x

echo "IN BOOTSTRAP ACCOUNTS"

(

# Parse input parameters...
#
# bootstrap account file
bootstrap_user_file=${1:-'/var/scitran/code/api/bootstrap.json.sample'}

# Create root user
#
BOOTSTRAPUSER_EMAIL=${2:-'bootstrap.user@flywheel.com'}
BOOTSTRAPUSER_FIRST_NAME=${3:-'bootstrapuser'}
BOOTSTRAPUSER_LAST_NAME=${4:-'bootstrapuser'}
BOOTSTRAPUSER_KEY=$(curl -k -X POST $SCITRAN_SITE_API_URL/users -d '{"_id": "'$BOOTSTRAPUSER_EMAIL'", "firstname": "'$BOOTSTRAPUSER_FIRST_NAME'", "lastname": "'$BOOTSTRAPUSER_LAST_NAME'"}' \
                  | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])")

echo "SCITRAN_CORE_API_KEY=$BOOTSTRAPUSER_KEY" > /dev.dynamic.env

# Move to API folder for relative path assumptions later on
#
cd /var/scitran/code/api

# Export PYTHONPATH for python script later on.
#
export PYTHONPATH=.


# Bootstrap Users
./bin/load_users_drone_secret.py --insecure --secret "${SCITRAN_CORE_DRONE_SECRET}" "${SCITRAN_SITE_API_URL}" "${bootstrap_user_file}"


)
