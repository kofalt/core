#!/bin/bash
set -e

# Create the bootsrap user. When the db is empty the first POST request to the 
# /api/users endpoint creates the root user and returns with the credentials
# $1 - User Id
# $2 - First name
# $3 - Last name
function CreateBootstrapUser() {(

  BOOTSTRAP_USER_EMAIL=${1:-'bootstrap.user@flywheel.com'}
  BOOTSTRAP_USER_FIRST_NAME=${2:-'bootstrapuser'}
  BOOTSTRAP_USER_LAST_NAME=${3:-'bootstrapuser'}
  BOOTSTRAP_USER_KEY=$(curl -k -X POST $SCITRAN_SITE_API_URL/users -d '{"_id": "'$BOOTSTRAP_USER_EMAIL'", "firstname": "'$BOOTSTRAP_USER_FIRST_NAME'", "lastname": "'$BOOTSTRAP_USER_LAST_NAME'"}' \
                    | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])")

  echo "SCITRAN_CORE_API_KEY=$BOOTSTRAP_USER_KEY" > /dev.dynamic.env
)}

echo "================================================"
echo "            CREATE BOOTSTRAP USER               "
echo "================================================"
CreateBootstrapUser $@
