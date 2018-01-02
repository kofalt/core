#!/bin/bash

set -euo pipefail

M2_REPO=/var/maven/.m2/repository

MATLAB_CODEGEN_VERSION=1.0.0

SWAGGER_VERSION=2.3.0
SWAGGER_CLI_JAR=${M2_REPO}/io/swagger/swagger-codegen-cli/${SWAGGER_VERSION}/swagger-codegen-cli-${SWAGGER_VERSION}.jar

MVN="mvn -Dmaven.repo.local=${M2_REPO}"
MATLAB_JAR="codegen/target/matlab-swagger-codegen-${MATLAB_CODEGEN_VERSION}.jar"

function usage() {
cat >&2 <<EOF
Generate swagger client code.
Usage:
	$0 [OPTION...]

Generates all languages if no options are provided

Options:
	-p, --python              Generate Python
	-m, --matlab              Generate Matlab
	-h, --help                Print this help and exit
EOF
}


function main() {
	export GEN_ALL=true
	export GEN_PYTHON=false
	export GEN_MATLAB=false

	while [[ "$#" > 0 ]]; do
		case "$1" in
			-p|--python)	GEN_ALL=false; GEN_PYTHON=true		;;
			-m|--matlab)	GEN_ALL=false; GEN_MATLAB=true		;;
			-h|--help)      usage; exit 0;						;;
			*) echo "Invalid argument: $1" >&2; usage; exit 1   ;;
		esac
		shift
	done
	
	if ${GEN_ALL}; then
		GEN_PYTHON=true
		GEN_MATLAB=true
	fi

	if [ ! -f ${SWAGGER_CLI_JAR} ]; then
		${MVN} dependency:get -Dartifact=io.swagger:swagger-codegen-cli:${SWAGGER_VERSION}
	fi

	# Python codegen
	if ${GEN_PYTHON}; then
		java -jar ${SWAGGER_CLI_JAR} generate -i swagger.json -l python -o src/python/flywheel/gen
	fi

	# Matlab codegen
	if ${GEN_MATLAB}; then
		${MVN} -f codegen/pom.xml package
		java -cp ${MATLAB_JAR}:${SWAGGER_CLI_JAR} io.swagger.codegen.SwaggerCodegen generate -i swagger.json -l matlab -o src/matlab/gen
	fi
}


main "$@"

