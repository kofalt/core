"""Returns appropriate storage provider based on the url provided"""
from .py_fs_storage import PyFsStorage
def create_flywheel_fs(url):

    if url.startswith('gc'):
        return PyFsStorage(url)
    if url.startswith('osfs'):
        return PyFsStorage(url)

    raise ValueError('Invalid storage url supplied')
