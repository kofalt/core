"""Returns appropriate storage provider based on the url provided"""
from .py_fs_storage import PyFsStorage

def create_flywheel_fs(url):
    """
    This loads the storage provider based on the url provided
    """
    if url.startswith('gc::/'):
        return PyFsStorage(url)
    if url.startswith('osfs://'):
        return PyFsStorage(url)

    # Assume the rest are paths which we can use with osfs even though they are not urls
    return PyFsStorage(url)
