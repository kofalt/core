#!/bin/bash

set -euo pipefail

java -jar /var/maven/.m2/repository/io/swagger/swagger-codegen-cli/2.3.0/swagger-codegen-cli-2.3.0.jar generate -i swagger.json -l python -o src/python/flywheel/gen


