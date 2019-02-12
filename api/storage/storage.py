from abc import ABCMeta, abstractmethod

class Storage(object):
    """Abstract class for filessytem objects"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def open(self, uuid, path_hint, mode, options):
        """
        Open a file like object

        :param self: self reference
        :param uid: internal id of file reference
        :param path_hint: local relative path for file location
        :param mode: Mode to open file
        :param options: Options list to pass to underlying storage layer
        :type uid: string
        :type path_hint: string
        :type mode: string
        :type options: list
        :returns: An object implemeting a file like interface
        :rtype: File

        """
        raise NotImplementedError()

    @abstractmethod
    def is_signed_url(self):
        """
        Return boolean if signed url is possible for this file type

        :param self: self reference
        :returns boolean:
        """
        raise NotImplementedError()
    
    @abstractmethod
    def get_signed_url(self, uuid, path_hint, purpose, filename, attachment=True, response_type=None):
        """
        Returns the signed url location of the file reference

        :param self: self reference
        :param string uuid: internal file uuid reference
        :param string path_hint: internal reference to file object on storage, used when uuid is not available
        :param string purpose: stated reason for signed url: upload or download
        :param string filename: Name of the downloaded file, used in the content-disposition header
        :param boolean attachment: True/False, attachment or not
        :param string response_type: Content-Type header of the response
        :return: string, the signed url string for accessing the referenced file
        :raises: ResourceNotFound, FileExpected, NoURL
        :rtype: string

        """
        raise NotImplementedError()
    
    @abstractmethod
    def get_file_hash(self, uuid, path_hint):
        """
        Returns the calculated hash for the current contents of the referenced file

        :param self: self reference
        :param string uuid: internal file uuid reference
        :param string path_hint: internal reference to the file object on storage, used when uuid is not available
        :returns: The hash value of the curreent file contents
        :rtype: string
        """
        raise NotImplementedError()

    #abstractmethod
    def get_file_info(self, uuid, path_hint):
        """
        Returns basic file info about the referenced file object, None if the file does not exist

        :param self: self reference
        :param string uuid: internal fild uuid reference
        :param path_hint string: internal reference to the file object on stroage, used when uuid is not available
        :returns: Dict of file information with the following data attributes
            {
                'filesize': int,
            }
        :rtype: Dict | None
        
        """
        raise NotImplementedError()

