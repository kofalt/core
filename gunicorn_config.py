import multiprocessing
import os

from prometheus_client import multiprocess


pythonpath = '/src/core'

bind = '0.0.0.0:8080'
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 600 
worker_class = 'gevent'

# Capture stdout/stderr to uwsgi.log
capture_output = True


# Prometheus/multiproc/gunicorn compatibility
# https://github.com/prometheus/client_python#multiprocess-mode-gunicorn
def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
