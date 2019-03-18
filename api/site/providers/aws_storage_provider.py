""" Provides the AWS S3 Storage Provider """
import datetime
import hashlib
import hmac
import requests
import uuid

from flywheel_common.storage import create_flywheel_fs
from ...web import errors
from .factory import ProviderKey
from ..models import ProviderClass
from .base import BaseProvider

# pylint: disable=too-few-public-methods
class AWSStorageProvider(BaseProvider):
    """The AWS S3 Storage provider object."""

    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(ProviderClass.storage, 'aws')

    def __init__(self, config):

        super(AWSStorageProvider, self).__init__(config)

        self._storage_plugin = None
        # we assume validation was done on persist so the keys should all be there
        #self.validate_config()
    
        # URL used to instantiate the storage plugin provider
        # URL in the format of s3://<<bucket-Name>/<path>
        self._storage_url = 's3://' + self.config['bucket'] + '/' + self.config.get('path', '')
        self._storage_plugin = create_flywheel_fs(self._storage_url)


    def validate_config(self):
        """
            Confirms the minimum required config is set
        """

        if not self.config:
            raise errors.APIValidationException('AWS S3 configuration is required')

        if not self.config.get('access_key'):
            raise errors.APIValidationException('AWS S3 requires access_key be set')

        if not self.config.get('secret_access_key'):
            raise errors.APIValidationException('AWS S3 requires secret_access_key be set')

        if not self.config.get('region'):
            raise errors.APIValidationException('AWS S3 requires region be set')

        if not self.config.get('bucket'):
            raise errors.APIValidationException('AWS S3 requires bucket be set')

        # We need to have a valid storage object set to run these
        if self._storage_plugin:
            self._validate_permissions()
            self._test_files()

    def get_redacted_config(self):
        return {
            'access_key': None,
            'secret_access_key': None,
            'region': self.config['region'],
            'bucket': self.config['bucket'],
            'path': self.config.get('path', None)
        }

    def _validate_permissions(self):
        """
            Do a permission check on the service account key permissions
        """

        s3_host = 's3.' + self.config['region'] + '.amazonaws.com'
        # list all the buckets we can see
        response = self._make_request('GET', '', s3_host)
        if response.status_code == 403:
            raise errors.APIValidationException('Unable to authenticate. Be sure the access_key and secret_access_key are correct')

        # This is for owners of the bucket. Can we assume the service account will own the bucket?
        if not '<Bucket><Name>' + self.config['bucket'] + '</Name>' in response.text:
            raise errors.APIValidationException('Unable to find your bucket. Be sure the bucket is configured correctly')

        # TODO: determine the way to validate we have only the permissions required and no more
        return True

    def _test_files(self):
        """
            Use the provider to upload to the bucket and then read from the bucket
            This is seperated so that we can use the provider after we verify the keys are correct
        """

        test_uuid = str(uuid.uuid4())

        # TODO wrap these in try blocks and catch the errors as we go
        test_file = self._storage_plugin.open(test_uuid, 'wb')
        test_file.write('This is a permissions test')
        test_file.close()

        test_file = self._storage_plugin.open(test_uuid, 'rb')
        test_file.read()
        test_file.close()

        self._storage_plugin.remove_file(test_uuid)

    @property
    def storage_url(self):
        """
            Allow access to the internal storage url
            This will not be needed once the url is removed from the storage factory
        """
        return self._storage_url

    @property
    def storage_plugin(self):
        """
            Allow access to the internal storage provider
        """
        return self._storage_plugin

    def _make_request(self, method, request_parameters, host):
        """
        # AWS API request generator modified from
        # https://docs.aws.amazon.com/general/latest/gr/sigv4-signed-request-examples.html
        # S3 requires the extra header of x-amz-content-sha256': payload_hash

        :param self: self reference
        :param string method: Upper case method for the request
        :param string request_parameters: String of the parmeters to append to the request
        :rtype request
        """

        # method = 'GET'
        method = method.upper()
        service = 's3'
        region = self.config['region']
        # host = 's3.' + region + '.amazonaws.com'
        # endpoint = 'https://s3.' + region + '.amazonaws.com'
        endpoint = 'https://' + host
        # request_parameters = 'Action=DescribeRegions&Version=2013-10-15'

        # Read AWS access key from env. variables or configuration file. Best practice is NOT
        # to embed credentials in code.
        access_key = self.config['access_key']
        secret_key = self.config['secret_access_key']

        # Create a date for headers and the credential string
        t = datetime.datetime.utcnow()
        amzdate = t.strftime('%Y%m%dT%H%M%SZ')
        datestamp = t.strftime('%Y%m%d') # Date w/o time, used in credential scope

        # ************* TASK 1: CREATE A CANONICAL REQUEST *************
        # http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html

        # Step 1 is to define the verb (GET, POST, etc.)--already done.

        # Step 2: Create canonical URI--the part of the URI from domain to query 
        # string (use '/' if no path)
        canonical_uri = '/' 

        # Step 3: Create the canonical query string. In this example (a GET request),
        # request parameters are in the query string. Query string values must
        # be URL-encoded (space=%20). The parameters must be sorted by name.
        # For this example, the query string is pre-formatted in the request_parameters variable.
        canonical_querystring = request_parameters

        # Step 4: Create the canonical headers and signed headers. Header names
        # must be trimmed and lowercase, and sorted in code point order from
        # low to high. Note that there is a trailing \n.
        canonical_headers = 'host:' + host + '\n' + 'x-amz-date:' + amzdate + '\n'

        # Step 5: Create the list of signed headers. This lists the headers
        # in the canonical_headers list, delimited with ";" and in alpha order.
        # Note: The request can include any headers; canonical_headers and
        # signed_headers lists those that you want to be included in the 
        # hash of the request. "Host" and "x-amz-date" are always required.
        signed_headers = 'host;x-amz-date'

        # Step 6: Create payload hash (hash of the request body content). For GET
        # requests, the payload is an empty string ("").
        payload_hash = hashlib.sha256(('').encode('utf-8')).hexdigest()

        # Step 7: Combine elements to create canonical request
        canonical_request = method + '\n' + canonical_uri + '\n' + canonical_querystring + '\n' + canonical_headers + '\n' + signed_headers + '\n' + payload_hash


        # ************* TASK 2: CREATE THE STRING TO SIGN*************
        # Match the algorithm to the hashing algorithm you use, either SHA-1 or
        # SHA-256 (recommended)
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = datestamp + '/' + region + '/' + service + '/' + 'aws4_request'
        string_to_sign = algorithm + '\n' +  amzdate + '\n' +  credential_scope + '\n' +  hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()

        # ************* TASK 3: CALCULATE THE SIGNATURE *************
        # Create the signing key using the function defined above.
        signing_key = self._get_signature_key(secret_key, datestamp, region, service)

        # Sign the string_to_sign using the signing_key
        signature = hmac.new(signing_key, (string_to_sign).encode('utf-8'), hashlib.sha256).hexdigest()


        # ************* TASK 4: ADD SIGNING INFORMATION TO THE REQUEST *************
        # The signing information can be either in a query string value or in 
        # a header named Authorization. This code shows how to use a header.
        # Create authorization header and add to request headers
        authorization_header = algorithm + ' ' + 'Credential=' + access_key + '/' + credential_scope + ', ' +  'SignedHeaders=' + signed_headers + ', ' + 'Signature=' + signature

        # The request can include any headers, but MUST include "host", "x-amz-date", 
        # and (for this scenario) "Authorization". "host" and "x-amz-date" must
        # be included in the canonical_headers and signed_headers, as noted
        # earlier. Order here is not significant.
        # Python note: The 'host' header is added automatically by the Python 'requests' library.
        headers = {'x-amz-date':amzdate, 'Authorization':authorization_header, 'x-amz-content-sha256': payload_hash}


        # ************* SEND THE REQUEST *************
        request_url = endpoint + '?' + canonical_querystring

        r = requests.get(request_url, headers=headers)
        return r
        # print('\nRESPONSE++++++++++++++++++++++++++++++++++++')
        # print('Response code: %d\n' % r.status_code)
        # print(r.text)

    # Key derivation functions. See:
    # http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
    def _get_signature_key(self, key, date_stamp, region_name, service_name):
        k_date = self._sign(('AWS4' + key).encode('utf-8'), date_stamp)
        k_region = self._sign(k_date, region_name)
        k_service = self._sign(k_region, service_name)
        k_signing = self._sign(k_service, 'aws4_request')
        return k_signing

    def _sign(self, key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
