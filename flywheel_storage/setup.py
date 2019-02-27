"""Loads flywheel storage packages in the namespace for osfs"""
from setuptools import setup, find_packages

setup(
    name='flywheel-storage',
    namespace_packages=['flywheel_storage'],
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'flywheel.storage': [
            'osfs = flywheel_storage.py_fs.py_fs_storage:PyFsStorage',
            'gc = flywheel_storage.py_fs.py_fs_storage:PyFsStorage',
        ]
    }
)
