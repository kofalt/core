# build - configure and build nginx unit, python requirements
FROM python:2.7-alpine3.7 as build

RUN apk --no-cache add git build-base linux-headers curl openssl-dev libffi-dev python3-dev

WORKDIR /src/nginx-unit

RUN curl -L https://github.com/nginx/unit/archive/1.3.tar.gz | tar xz --strip-components 1
RUN ./configure --prefix=/usr/local --modules=lib --state=/var/local/unit --pid=/var/unit.pid --log=/var/log/unit.log \
	&& ./configure python \
	&& make install

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt

# base - install common dependencies & create directories
FROM python:2.7-alpine3.7 as base

COPY --from=build /usr /usr

EXPOSE 80 8088
VOLUME /data/db /data/persistent

WORKDIR /src/core
ENV SCITRAN_PERSISTENT_DATA_PATH=/data/persistent

COPY nginx-unit.json /var/local/unit/conf.json

CMD ["unitd", "--control", "*:8088", "--no-daemon", "--log", "/dev/stdout"]

# dist - install requirements & core
FROM base as dist

COPY . /src/core
RUN pip install --no-deps -e /src/core

ARG API_VERSION=''
ARG VCS_BRANCH=NULL
ARG VCS_COMMIT=NULL
RUN echo $API_VERSION > /src/core/api/api_version.txt \
    && /src/core/bin/build_info.sh $VCS_BRANCH $VCS_COMMIT > /src/core/version.json \
    && cat /src/core/version.json

# testing - install mongodb & test deps for standalone running/testing
FROM base as testing

EXPOSE 27017

RUN apk add --no-cache mongodb
RUN mkdir -p /data/db

COPY . /src/core
RUN pip install -r /src/core/tests/requirements.txt
RUN pip install --no-deps -e /src/core

# TODO uncomment once compatible with fly/fly
# # make dist the last (default) build target
# FROM dist
