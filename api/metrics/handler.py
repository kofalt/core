""" Prometheus Client Metrics request handler """
from prometheus_client import multiprocess
from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST

from ..web import base

class MetricsHandler(base.RequestHandler):
    # TODO: Needs authentication!!!
    def get(self):
        """ Generate the latest metrics for the Prometheus Scraper """
        def metrics_handler(_, start_response):
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)

            data = generate_latest(registry)

            # Notify mule that metrics have been collected
            try:
                import uwsgi
                uwsgi.farm_msg('metrics', 'collect-metrics')
            except ImportError:
                self.log.exception('Could not notify mule to collect metrics')

            write = start_response('200 OK', [
                ('Content-Type', CONTENT_TYPE_LATEST),
                ('Content-Length', str(len(data)))
            ])

            write(data)
            return []

        return metrics_handler

