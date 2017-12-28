#!/bin/bash

set -euo pipefail

cmd=$1
if [ "$cmd" = "mvn" ]; then
    exec mvn -Dmaven.repo.local=/var/maven/.m2/repository "${@:2}"
elif [ "$cmd" = "codegen" ]; then
	exec java -jar /var/maven/.m2/repository/io/swagger/swagger-codegen-cli/2.3.0/swagger-codegen-cli-2.3.0.jar "${@:2}"
else
    exec "$@"
fi


