"""Provides factory function for DownloadStrategies"""
from .bulk import BulkDownloadStrategy
from .classic import ClassicDownloadStrategy
from .full import FullDownloadStrategy


_strategies = {
    'classic': ClassicDownloadStrategy,
    'bulk': BulkDownloadStrategy,
    'full': FullDownloadStrategy,
}


# For lack of a better place for now...
def create_download_strategy(name, log, params):
    """Get a DownloadStrategy by name.

    Args:
        name (str): The name of the strategy to create
        log (Logger): The logger instance to use for logging
        params (dict): Additional parameters to pass to the logging strategy

    Returns:
        DownloadStrategy: The download strategy instance, or None
    """
    strategy = _strategies.get(name, None)
    if strategy is not None:
        return strategy(log=log, params=params)

    return None

