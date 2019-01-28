from abc import ABCMeta, abstractmethod

class Storage(object):
    """Abstract class for filessytem objects"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def open(self, uid, path_hint, mode, options):
        """
        Open a file like object

        :param self: self reference
        :param uid: string
        :param path_hint: strig
        :param mode: string
        :param options list
        :rtype: File

        """
        raise NotImplementedError()

    @abstractmethod
    def is_signed_url(self):
        """
        Return boolean if signed url is possible for this file type
        """
        raise NotImplementedError()
    
    @abstractmethod
    def get_signed_url(self, id, path_hint, purpose):
        raise NotImplementedError()
    
    @abstractmethod
    def get_file_hash(self, id, path_hint):
        raise NotImplementedError()

