""" Prometheus Client Metrics request handler """
from prometheus_client import multiprocess
from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST

from .collect import collect_metrics
from ..web import base

class MetricsHandler(base.RequestHandler):
    # NOTE: Unauthenticated due to internal exposure only
    def get(self):
        """ Generate the latest metrics for the Prometheus Scraper """
        def metrics_handler(_, start_response):
            # Collect (if force_collect=true)
            if self.is_true('force_collect'):
                # NOTE: This flag should be used for testing only
                # It will cause metrics to be incorrect if used in production
                self.log.critical('Serving metrics after forced collection!')
                collect_metrics()

            # Fulfill the request
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)

            data = generate_latest(registry)

            write = start_response('200 OK', [
                ('Content-Type', CONTENT_TYPE_LATEST),
                ('Content-Length', str(len(data)))
            ])

            write(data)
            return []

        return metrics_handler

