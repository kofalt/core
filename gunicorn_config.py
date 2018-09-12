import multiprocessing

pythonpath = '/src/core'

bind = '0.0.0.0:8080'
workers = multiprocessing.cpu_count() * 2 + 1

user = 'root'
group = 'root'

capture_output = True

