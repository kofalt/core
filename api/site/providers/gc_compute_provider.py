""" Provides the Google Cloud Compute Provider """
import datetime
import requests
import jwt

from ...web import errors
from .compute_provider import ComputeProvider
from .factory import ProviderKey
from ..models import ProviderClass
from ...config import log

# pylint: disable=too-few-public-methods
class GCComputeProvider(ComputeProvider):
    """The Google Cloud compute provider object."""

    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(ProviderClass.compute, 'gc')

    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://accounts.google.com/o/oauth2/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"

    # Note the following services must be enabled in the API settings for this code to work
    #    #Service Usage API
    #    #Identity and Access Management (IAM) API
    #    Cloud Resource Manager API


    def validate_config(self):
        """
            Confirms the minimum required config is set
        """

        if not self.config:
            raise errors.APIValidationException('Google Compute configuration is required')

        if not self.config.get('client_id'):
            raise errors.APIValidationException('Google Compute requires client_id be set')

        if not self.config.get('client_email'):
            raise errors.APIValidationException('Google Compute requires client_email be set')

        if not self.config.get('private_key_id'):
            raise errors.APIValidationException('Google Compute requires private_key_id be set')

        if not self.config.get('private_key'):
            raise errors.APIValidationException('Google Compute requires private_key be set')

        if not self.config.get('client_x509_cert_url'):
            raise errors.APIValidationException('Google Compute requires client_x509_cert_url be set')

        if not self.config.get('project_id'):
            raise errors.APIValidationException('Google Compute requires project_id be set')

        self._validate_permissions()


    def _validate_permissions(self):
        """
            Does a permission check by calling the Cloud Resource API with a static list of
            permission that are required for a functioning GC compute instance. In time we will
            add in the inverse validation to confirm that only those permissions are enabled on the
            service account
        """

        # First get a token to check permissions
        data = {
            "iss": self.config['client_email'],
            # TODO: remove the IAM scope if we decide not to use it
            "scope": "https://www.googleapis.com/auth/iam https://www.googleapis.com/auth/cloud-platform.read-only",
            "aud": "https://www.googleapis.com/oauth2/v4/token",
            "exp": datetime.datetime.now() + datetime.timedelta(minutes=60),
            "iat": datetime.datetime.now()
        }
        encoded_jwt = jwt.encode(data, self.config['private_key'], algorithm='RS256')
        payload = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': encoded_jwt
        }

        response = requests.post('https://www.googleapis.com/oauth2/v4/token', data=payload)
        if response.status_code != 200:
            log.error(response.raw)
            raise errors.APIValidationException('Unable to authenticate. Be sure the client_id and private_key are correct')
        token = response.json().get('access_token')

        # Check all the permissions but the api limits us to 100 at a time so loop as needed
        headers = {
            'Authorization': 'Bearer ' + token
        }

        i = 0
        missing = []
        while True:
            small_perms = PERMS[100*i: 100*(i+1)]

            if not small_perms:
                break

            payload = {
                'permissions': small_perms
            }

            # Using cloud resource manager we can check the permissions for the current user without any permissions
            # But the Cloud Resource Manager API must be enabled in the project
            response = requests.post('https://cloudresourcemanager.googleapis.com/v1/projects/{}:testIamPermissions/' \
                .format(self.config['project_id']),
                                     headers=headers,
                                     data=payload)

            if response.status_code == 403:
                error = response.json()
                if 'Cloud Resource Manager API has not been used' in error['error']['message']:
                    raise errors.APIValidationException("You need to enable the Clour Resource Manager API for your project")
                else: # All other permission errors but the API has been enabled
                    log.error(error['error']['message'])
                    # TODO test to see what else causes 403 errors on this API and filter out is possible
                    raise errors.APIValidationException(error['error']['message'])

            if response.status_code == 404:
                error = response.json()
                log.error(response.raw)
                raise errors.APIValidationException('Unable to validate permissions. Be sure the procject_id is correct')

            if response.status_code != 200:
                log.error(response.raw)
                raise errors.APIValidationException("Error validating permissions")

            r = response.json()
            if r.get('permissions') and len(r['permissions']) != len(small_perms):
                missing += list(set(small_perms) - set(r['permissions']))
            i += 1

        if missing:
            print 'We are missing {} permissions out of {}'.format(len(missing), len(PERMS))
            raise errors.APIValidationException('Your account is missing the following permissions' + ' '.join(missing))


PERMS = [
    'compute.acceleratorTypes.get',
    'compute.acceleratorTypes.list',
    'compute.addresses.get',
    'compute.addresses.list',
    'compute.addresses.use',
    'compute.autoscalers.create',
    'compute.autoscalers.delete',
    'compute.autoscalers.get',
    'compute.autoscalers.list',
    'compute.autoscalers.update',
    'compute.backendBuckets.get',
    'compute.backendBuckets.list',
    'compute.backendServices.get',
    'compute.backendServices.list',
    'compute.clientSslPolicies.get',
    'compute.clientSslPolicies.list',
    'compute.disks.create',
    'compute.disks.createSnapshot',
    'compute.disks.delete',
    'compute.disks.get',
    'compute.disks.getIamPolicy',
    'compute.disks.list',
    'compute.disks.resize',
    'compute.disks.setIamPolicy',
    'compute.disks.setLabels',
    'compute.disks.update',
    'compute.disks.use',
    #'compute.disks.*',
    'compute.disks.useReadOnly',
    'compute.diskTypes.get',
    'compute.diskTypes.list',
    'compute.firewalls.get',
    'compute.firewalls.list',
    'compute.forwardingRules.get',
    'compute.forwardingRules.list',
    'compute.globalAddresses.get',
    'compute.globalAddresses.list',
    'compute.globalAddresses.use',
    'compute.globalForwardingRules.get',
    'compute.globalForwardingRules.list',
    'compute.globalOperations.get',
    'compute.globalOperations.list',
    'compute.healthChecks.get',
    'compute.healthChecks.list',
    'compute.httpHealthChecks.get',
    'compute.httpHealthChecks.list',
    'compute.httpsHealthChecks.get',
    'compute.httpsHealthChecks.list',
    'compute.images.create',
    'compute.images.delete',
    'compute.images.deprecate',
    'compute.images.get',
    'compute.imageo.getFromFamily',
    'compute.images.getIamPolicy',
    'compute.images.list',
    'compute.images.setIamPolicy',
    'compute.images.setLabels',
    'compute.images.update',
    'compute.images.useReadOnly',
    'compute.instanceGroupManagers.create',
    'compute.instanceGroupManagers.delete',
    'compute.instanceGroupManagers.get',
    'compute.instanceGroupManagers.list',
    'compute.instanceGroupManagers.update',
    'compute.instanceGroupManagers.use',
    'compute.instanceGroups.create',
    'compute.instanceGroups.delete',
    'compute.instanceGroups.get',
    'compute.instanceGroups.list',
    'compute.instanceGroups.update',
    'compute.instanceGroups.use',
    'compute.instances.addAddressConfig',
    'compute.instances.addMaintenancePolicies',
    'compute.instances.attachDisk',
    'compute.instances.create',
    'compute.instances.delete',
    'compute.instances.deleteAccessConfig',
    'compute.instances.detachDisk',
    'compute.instances.get',
    'compute.instances.getGuestAttributes',
    'compute.instances.getIamPolicy',
    'compute.instances.getSerialPortOutput',
    'compute.instances.list',
    'compute.instances.listReferrers',
    'compute.instances.osAdminLogin',
    'compute.instances.osLogin',
    'compute.instances.removeMaintenancePolicies',
    'compute.instances.reset',
    'compute.instances.resume',
    'compute.instances.setDeletionProtection',
    'compute.instances.setDiskAutoDelete',
    'compute.instances.setIamPolicy',
    'compute.instances.setLabels',
    'compute.instances.setMachineResources',
    'compute.instances.setMachineType',
    'compute.instances.setMetadata',
    'compute.instances.setMinCpuPlatform',
    'compute.instances.setScheduling',
    'compute.instances.setServiceAccount',
    'compute.instances.setShieldedVmIntegrityPolicy',
    'compute.instances.setTags',
    'compute.instances.start',
    'compute.instances.startWithEncryptionKey',
    'compute.instances.stop',
    'compute.instances.suspend',
    'compute.instances.updateAccessConfig',
    'compute.instances.updateNetworkInterface',
    'compute.instances.updateShieldedVmConfig',
    'compute.instances.use',
    'compute.instanceTemplates.create',
    'compute.instanceTemplates.delete',
    'compute.instanceTemplates.get',
    'compute.instanceTemplates.getIamPolicy',
    'compute.instanceTemplates.list',
    'compute.instanceTemplates.setIamPolicy',
    'compute.instanceTemplates.useReadOnly',
    'compute.interconnectAttachments.get',
    'compute.interconnectAttachments.list',
    'compute.interconnectLocations.get',
    'compute.interconnectLocations.list',
    'compute.interconnects.get',
    'compute.interconnects.list',
    #'compute.licenses.*',
    #'compute.licenseCodes.*',
    'compute.machineTypes.get',
    'compute.machineTypes.list',
    #'compute.networkEndpointGroups.*',
    'compute.networks.get',
    'compute.networks.list',
    'compute.networks.use',
    'compute.networks.useExternalIp',
    'compute.regionOperations.get',
    'compute.regionOperations.list',
    'compute.regions.get',
    'compute.regions.list',
    'compute.routers.get',
    'compute.routers.list',
    'compute.routes.get',
    'compute.routes.list',
    #'compute.snapshots.*',
    'compute.sslCertificates.get',
    'compute.sslCertificates.list',
    'compute.sslPolicies.get',
    'compute.sslPolicies.list',
    'compute.subnetworks.get',
    'compute.subnetworks.list',
    'compute.subnetworks.use',
    'compute.subnetworks.useExternalIp',
    'compute.targetHttpProxies.get',
    'compute.targetHttpProxies.list',
    'compute.targetHttpsProxies.get',
    'compute.targetHttpsProxies.list',
    'compute.targetInstances.get',
    'compute.targetInstances.list',
    'compute.targetPools.get',
    'compute.targetPools.list',
    'compute.targetSslProxies.get',
    'compute.targetSslProxies.list',
    'compute.targetTcpProxies.get',
    'compute.targetTcpProxies.list',
    'compute.targetVpnGateways.get',
    'compute.targetVpnGateways.list',
    'compute.urlMaps.get',
    'compute.urlMaps.list',
    'compute.vpnTunnels.get',
    'compute.vpnTunnels.list',
    'compute.zoneOperations.get',
    'compute.zoneOperations.list',
    'compute.zones.get',
    'compute.zones.list',
    'compute.projects.get',
    'compute.projects.setCommonInstanceMetadata'
]
