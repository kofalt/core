# base - install common dependencies & create directories
FROM python:2.7-alpine3.8 as base
RUN set -eux \
    && apk add --no-cache \
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
        gunicorn[gevent] \
    && mkdir -p \
        # TODO simplify/unify structure:
        /var/scitran/data \
        /var/scitran/keys \
        /var/scitran/logs
COPY requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt
EXPOSE 8080
VOLUME /var/scitran/data
VOLUME /var/scitran/keys
VOLUME /var/scitran/logs
WORKDIR /src/core
ENV SCITRAN_PERSISTENT_DATA_PATH=/var/scitran/data
COPY docker/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--reload", "-c", "/src/core/gunicorn_config.py", "api.app"]

# dist - install requirements & core
FROM base as dist
COPY . /src/core
RUN pip install --no-deps -e /src/core
ARG API_VERSION=''
ARG VCS_BRANCH=NULL
ARG VCS_COMMIT=NULL
RUN set -eux \
    && echo $API_VERSION > /src/core/api_version.txt \
    && /src/core/bin/build_info.sh $VCS_BRANCH $VCS_COMMIT > /src/core/version.json \
    && cat /src/core/version.json
VOLUME "/src/core/core.egg-info"

# testing - install mongodb & test deps for standalone running/testing
FROM base as testing
RUN set -eux \
    && apk add --no-cache mongodb \
    && mkdir -p /data/db
VOLUME /data/db
EXPOSE 27017
COPY tests/requirements.txt /src/core/tests/requirements.txt
COPY docker/config/logging /src/core/logging
RUN pip install -r /src/core/tests/requirements.txt
COPY . /src/core
RUN pip install --no-deps -e /src/core
VOLUME "/src/core/core.egg-info"

FROM testing as live
COPY docker/live-entrypoint.sh /entrypoint.sh

# TODO uncomment once compatible with fly/fly
# # make dist the last (default) build target
# FROM dist
