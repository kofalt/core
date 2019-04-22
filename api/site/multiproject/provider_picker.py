"""Strategy for picking providers for certain tasks"""
from abc import ABCMeta, abstractmethod

class ProviderPicker(object):
    """Abstract picker strategy for providers"""
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def get_provider_id_for_container(self, container, provider_class, site_settings=None):
        """Get the effective provider of type provider_class for the given container.

        Walks up the tree, as needed, stopping at site to determine the provider.

        Args:
            container (dict): The container under question.
            provider_class (ProviderClass|str): The class of provider to retrieve.
            site_settings (SiteSettings): Optional site_settings, if preloaded

        Returns:
            (bool, ObjectId): True if this is a site provider, and the provider id, if found, otherwise None
        """

    @abstractmethod
    def get_compute_provider_id_for_job(self, gear, destination, inputs):
        """Determine the compute provider for the given job profile.

        Args:
            gear (dict): The resolved gear document
            destination (dict): The destination container
            inputs (list(dict)): The list of input containers, with origins

        Returns:
            ObjectId: The id of the provider, or None if no applicable provider was found.

        Raises:
            APIValidationException: If invalid args were passed
        """
