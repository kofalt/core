"""Metrics collection worker with code reloading"""
import logging
import os
import time

from .collect import collect_metrics

log = logging.getLogger("metrics")


COLLECTION_INTERVAL_SECONDS = 30


def fork(post_fork):
    """Fork the current process into a metrics collection worker process.

    Args:
        post_fork (function): An optional function to call in the child process
    """
    child_pid = os.fork()
    if child_pid != 0:
        return

    # We're now the child process, so execute post_fork
    if post_fork is not None:
        post_fork()

    # Then run metrics collection every 30s until killed.
    while True:
        try:
            collect_metrics()
        except:  # pylint: disable=bare-except
            log.exception("Error collecting metrics")

        time.sleep(COLLECTION_INTERVAL_SECONDS)
