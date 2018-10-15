import multiprocessing
import os

pythonpath = '/src/core'

bind = '0.0.0.0:8080'
workers = multiprocessing.cpu_count() * 2 + 1

user = 'root'
group = 'root'

capture_output = True

prometheus_dir = '/tmp/prometheus'
os.environ['prometheus_multiproc_dir'] = prometheus_dir
if os.path.isdir(prometheus_dir):
    shutil.rmtree(prometheus_dir, ignore_errors=True)
os.makedirs(prometheus_dir)
