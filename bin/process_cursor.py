"""Provides functionality for processing a cursor as part of a DB script"""
import logging
import os


def get_monotonic_time():
    """Get a monotonically increasing timestamp.

    See: http://stackoverflow.com/a/7424304

    Return:
        A relative timestamp, in seconds.
    """
    return os.times()[4]


def process_cursor(cursor, closure, *args, **kwargs):
    """
    Given an iterable (say, a mongo cursor) and a closure, call that closure in parallel over the iterable.
    Call order is undefined. Currently launches N python process workers, where N is the number of vcpu cores.

    Useful for upgrades that need to touch each document in a database, and don't need an iteration order.

    Your closure MUST return True on success. Anything else is logged and treated as a failure.
    A closure that throws an exception will fail the upgrade immediately.
    """

    begin = get_monotonic_time()

    # cores = multiprocessing.cpu_count()
    # pool = multiprocessing.Pool(cores)
    # logging.info('Iterating over cursor with ' + str(cores) + ' workers')

    # # Launch all work, iterating over the cursor
    # # Note that this creates an array of n multiprocessing.pool.AsyncResults, where N is table size.
    # # Memory usage concern in the future? Doesn't seem to be an issue with ~120K records.
    # # Could be upgraded later with some yield trickery.
    # results = [pool.apply_async(closure, (document,)) for document in cursor]

    # # Read the results back, presumably in order!
    # failed = False
    # for res in results:
    # 	result = res.get()
    # 	if result != True:
    # 		failed = True
    # 		logging.info('Upgrade failed: ' + str(result))

    # logging.info('Waiting for workers to complete')
    # pool.close()
    # pool.join()

    logging.info("Proccessing {} items in cursor ...".format(cursor.count()))

    failed = False
    cursor_size = cursor.count()
    cursor_index = 0.0
    next_percent = 5.0
    percent_increment = 5
    if cursor_size < 20:
        next_percent = 25.0
        percent_increment = 25
    if cursor_size < 4:
        next_percent = 50.0
        percent_increment = 50
    for document in cursor:
        if 100 * (cursor_index / cursor_size) >= next_percent:
            logging.info("{} percent complete ...".format(next_percent))
            next_percent = next_percent + percent_increment
        result = closure(document, *args, **kwargs)
        cursor_index = cursor_index + 1
        if result != True:
            failed = True
            logging.info("Upgrade failed: " + str(result))

    if failed is True:
        msg = "Worker pool experienced one or more failures. See above logs."
        logging.info(msg)
        raise Exception(msg)

    end = get_monotonic_time()
    elapsed = end - begin
    logging.info("Parallel cursor iteration took " + ("%.2f" % elapsed))
