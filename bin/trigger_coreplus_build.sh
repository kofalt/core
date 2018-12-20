#/usr/bin/env sh
set -eux

USAGE="
Usage:
    $0 CORE_IMAGE_TAG

Trigger coreplus travis to build coreplus:CORE_IMAGE_TAG.

Required envvars:
    GITHUB_RELEASE_API_KEY
    TRAVIS_BRANCH
    TRAVIS_COMMIT
    TRAVIS_TAG
"

if [ $# -ne 1 ]; then
    printf "%s" "$USAGE" >&2
    exit 1
fi

CORE_IMAGE_TAG=$1
POST_DATA=$(cat <<EOF
{"request": {
    "branch": "master",
    "message": "Build triggered by core:$CORE_IMAGE_TAG",
    "config": {
        "env": {
            "CORE_TRIGGER":   "true",
            "CORE_COMMIT":    "$TRAVIS_COMMIT",
            "CORE_BRANCH":    "$TRAVIS_BRANCH",
            "CORE_TAG":       "$TRAVIS_TAG",
            "CORE_IMAGE_TAG": "$CORE_IMAGE_TAG"
        }
    }
}}
EOF
)

travis login --pro --no-interactive --github-token "$GITHUB_RELEASE_API_KEY"
curl --fail \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -H "Travis-API-Version: 3" \
    -H "User-Agent: Flywheel ci" \
    -H "Authorization: token $(travis token --pro --no-interactive)" \
    -d "$POST_DATA" \
    "https://api.travis-ci.com/repo/flywheel-io%2Fcoreplus/requests"
