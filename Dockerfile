# base - install common dependencies & create directories
FROM python:2.7-alpine3.8 as base

RUN apk add --no-cache \
        # TODO get rid of bash after updating all scripts
        bash \
        build-base \
        curl \
        git \
        libffi-dev \
        linux-headers \
        openssl-dev \
        py-pip \
        python-dev \
		su-exec \
    && pip install --upgrade \
        pip \
        setuptools \
        wheel \
		gunicorn[gevent]

COPY requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt

EXPOSE 80 8088
VOLUME /data/db /data/persistent

WORKDIR /src/core
ENV SCITRAN_PERSISTENT_DATA_PATH=/data/persistent

CMD ["gunicorn", "--reload", "-c" "/src/core/gunicorn_config.py", "api.app"]

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
