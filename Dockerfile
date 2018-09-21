# base - install common dependencies & create directories
FROM alpine:3.8 as base
ENV TERM=xterm
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
        uwsgi-http \
        uwsgi-python \
    && pip install --upgrade \
        pip \
        setuptools \
        wheel \
    && mkdir -p \
        # TODO simplify/unify structure:
        #  /var/scitran          -> /src/core
        #  /var/scitran/code/api -> /src/core/code
        /var/scitran/code/api \
        /var/scitran/config \
        /var/scitran/data \
        /var/scitran/keys \
        /var/scitran/logs
# TODO use workdir /src/core/code
WORKDIR /var/scitran
VOLUME /var/scitran/data
VOLUME /var/scitran/keys
VOLUME /var/scitran/logs
COPY docker/uwsgi-entrypoint.sh     /var/scitran/
COPY docker/uwsgi-config.ini        /var/scitran/config/
COPY docker/uwsgi-config.http.ini   /var/scitran/config/
ENTRYPOINT ["/var/scitran/uwsgi-entrypoint.sh"]
CMD ["uwsgi", "--ini=/var/scitran/config/uwsgi-config.http.ini", "--http-keepalive"]

# dist - install requirements & core
FROM base as dist
COPY requirements.txt /var/scitran/code/api/requirements.txt
RUN set -eux \
    && pip install --requirement /var/scitran/code/api/requirements.txt
COPY . /var/scitran/code/api/
RUN set -eux \
    && pip install --no-deps --editable /var/scitran/code/api
ARG API_VERSION=''
ARG VCS_BRANCH=NULL
ARG VCS_COMMIT=NULL
RUN set -eux \
    && echo $API_VERSION > /var/scitran/code/api/api_version.txt \
    && /var/scitran/code/api/bin/build_info.sh $VCS_BRANCH $VCS_COMMIT > /var/scitran/version.json \
    && cat /var/scitran/version.json

# testing - install mongodb & test deps for standalone running/testing
FROM base as testing
RUN set -eux \
    && apk add --no-cache \
        mongodb \
    && mkdir -p /data/db
COPY --from=dist /usr /usr
COPY tests/requirements.txt /var/scitran/code/api/tests/requirements.txt
RUN set -eux \
    && pip install --requirement /var/scitran/code/api/tests/requirements.txt
COPY --from=dist /var/scitran /var/scitran

# TODO uncomment once compatible with fly/fly
# # make dist the last (default) build target
# FROM dist
