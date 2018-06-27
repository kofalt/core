class APIException(Exception):
    """Base core exception class"""

    # HTTP status code returned
    status_code = 500

    # unique string status code
    # used when client needs more detail than HTTP status code can provide
    # optional
    core_status_code = None

    # default response msg
    default_msg = 'There was an error processing the request.'

    def __init__(self, msg=None, errors=None):
        if not msg:
            msg = self.default_msg
        super(APIException, self).__init__(msg)
        self.errors = errors

###
# Auth Exceptions
###

class APIAuthProviderException(APIException):
    """Authentication through 3rd party, session token, or API key failed"""
    status_code = 401
    default_msg = 'Unsuccessful authentication.'

class APIUnknownUserException(APIException):
    """Authentication was successful but user was not found or disabled"""
    status_code = 402
    default_msg = 'User could not be found or is disabled.'

class APIPermissionException(APIException):
    """User does not have permission to perform requested action"""
    status_code = 403
    default_msg = 'User does not have permission to perform requested action.'

    def __init__(self, msg, errors=None):

        super(APIPermissionException, self).__init__(msg)
        self.errors = errors

class APIRefreshTokenException(APIException):
    """
    Specifically alert a client when the user's refresh token expires
    Note: for some 3rd party auth providers, requires client to ask for `offline=true` permission to receive a new one
    """
    status_code = 401
    core_status_code = 'invalid_refresh_token'
    default_msg = 'User refresh token has expired.'


###
# Input Validation Exceptions
###

class InputValidationException(APIException):
    """Payload for a POST or PUT does not match input json schema"""
    status_code = 400
    default_msg = 'Input does not match input schema.'

# Probably doesn't need to be it's own class, should use InputValidationException
class APIReportParamsException(APIException):
    """Invalid or missing parameters for a report request"""
    status_code = 400
    default_msg = 'Report parameters are invalid.'

class APIValidationException(APIException):
    """Specially formatted reponse to allow clients to provide detailed information about input vaidation issue"""
    status_code = 422
    default_msg = 'Input does not match input schema.'

class FileFormException(APIException):
    """File Form for upload requests made by client is incorrect"""
    status_code = 400
    default_msg = 'File form upload request is incorrect.'

class FileStoreException(APIException):
    """?"""
    status_code = 400


###
# API Server Exceptions
###

class APINotFoundException(APIException):
    """The requested object could not be found"""
    status_code = 404
    default_msg = 'The resource could not be found.'

class APIConflictException(APIException):
    """
    There was an attempt to create a new object with the same unique key as another object
    Usually _id, but not limited to that key
    """
    status_code = 409
    default_msg = 'A resource with the same unique identification key already exists.'

class APIConsistencyException(APIException):
    """Legacy db consistency exception"""
    status_code = 400

class APIStorageException(APIException):
    """An error occurred while performing a CRUD action in the storage layer"""
    pass

class DBValidationException(APIException):
    """Legacy exception: payload did not match mongo json schema due to developer error"""
    pass

class APIReportException(APIException):
    """A non-user error occurred while attempting to generate a report"""
    pass
