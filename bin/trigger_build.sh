TRAVIS_TOKEN=$1

BUILD_SDK=$2

# Workaround not to trigger coreplus twice
if [[ "$BUILD_SDK" == "true" ]]; then
    echo "BUILD_SDK is set to $BUILD_SDK, do not trigger coreplus"
    exit 0
fi

#The repository whose CI is to be triggered
TARGET_REPO=$3

#The branch whose CI is to be triggered
TARGET_BRANCH=$4

# The name of the git branch in the triggering repo
# If it is a pull request it is set to TRAVIS_PULL_REQUEST_BRANCH
ORIGIN_BRANCH=$5

# The name of the git git in the triggering repo
ORIGIN_TAG=$6

# Here the environment that will be sent to the triggered CI is set
# ORIGIN_TAG is set to ORIGIN_TAG
# ORIGIN_GIT_REF is set to the tag if it exists otherwise it is set to the branch
# ORIGIN_IMAGE_TAG is the docker image tag to be used which is
#   - the tag
#   - branch.latest (if not master)
#   - latest (if on master)
# ORIGIN_IMAGE is set to "flywheel/core:$ORIGIN_BRANCH.latest"
if [[ -n $ORIGIN_TAG ]]; then
    ORIGIN_TAG=$ORIGIN_TAG
    ORIGIN_GIT_REF=$ORIGIN_TAG
    ORIGIN_IMAGE_TAG=$ORIGIN_TAG
else
    if [[ ${ORIGIN_BRANCH} == "master" ]]; then
        ORIGIN_IMAGE_TAG="latest"
    else
        ORIGIN_IMAGE_TAG="$ORIGIN_BRANCH.latest"
    fi
    ORIGIN_TAG=""
    ORIGIN_GIT_REF="origin/$ORIGIN_BRANCH"
fi

ORIGIN_IMAGE="flywheel/core:$ORIGIN_BRANCH.latest"

MESSAGE="Build triggered by image:$ORIGIN_IMAGE on branch: $ORIGIN_BRANCH"
POST_DATA="{\"request\": {\"branch\":\"$TARGET_BRANCH\", \"message\":\"$MESSAGE\", \"config\": {\"env\": {\"CORE_IMAGE\": \"$ORIGIN_IMAGE\", \"ORIGIN_GIT_REF\": \"$ORIGIN_GIT_REF\", \"ORIGIN_IMAGE_TAG\": \"$ORIGIN_IMAGE_TAG\", \"ORIGIN_TAG\": \"$ORIGIN_TAG\"}}}}"
curl -X POST -H "Content-Type: application/json" -H "Accept: application/json" -H "Travis-API-Version: 3" -H "User-Agent: Flywheel ci" -H "Authorization: token $TRAVIS_TOKEN" -d "$POST_DATA" https://api.travis-ci.com/repo/$TARGET_REPO/requests
