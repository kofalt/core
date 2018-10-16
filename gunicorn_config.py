import multiprocessing
import os

pythonpath = '/src/core'

bind = '0.0.0.0:8080'
workers = multiprocessing.cpu_count() * 2 + 1

if 'RUNAS_USER' in os.environ:
    print('[config] RUNAS_USER={}'.format(os.environ['RUNAS_USER']))
    user = int(os.environ['RUNAS_USER'])

# Capture stdout/stderr to uwsgi.log
capture_output = True
