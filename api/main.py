#!/usr/bin/env python
import argparse
import cherrypy

from .web import start

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CherryPy wsgi wrapper')

    parser.add_argument('--python-autoreload', action='store_true', help='Whether or not to turn on autoreload')
    parser.add_argument('--http', help='The http service listen interface')
    parser.add_argument('--socket', help='The socket (wsgi) service listen interface')
    parser.add_argument('--http-keepalive', action='store_true', help='Enable http keepalive')
    parser.add_argument('--so-keepalive', action='store_true', help='Enable socket keepalive')
    parser.add_argument('--add-header', action='append', help='Add headers to response objects')

    args, _ = parser.parse_known_args()

    # Initiate the application
    application = start.app_factory()
    cherrypy.tree.graft(application, '/')

    # Unsubscribe default server
    cherrypy.server.unsubscribe()

    # Set some global config
    cherrypy.config.update({
        'server.socket_timeout': 280,
        'server.max_request_body_size': 0,
        'response.timeout': 3600
    })

    # Setup server
    socket_str = args.http or args.socket or '[::]:8080'
    server = cherrypy._cpserver.Server()  # pylint: disable=protected-access
    _, _, port = socket_str.rpartition(':')

    server.socket_host = '0.0.0.0'
    server.socket_port = int(port)
    server.thread_pool = 30 #TODO: Determine best value here
    server.max_request_body_size = 0
    server.socket_timeout = 280

    server.subscribe()
    cherrypy.engine.start()
    cherrypy.engine.block()
