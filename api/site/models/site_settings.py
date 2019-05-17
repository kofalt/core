"""Provide the SiteSettings class"""
import datetime

from ... import models


class SiteSettings(models.Base):
    """Represents the global site configuration"""

    def __init__(self, center_gears, providers):
        """Create a new site settings.

        Args:
            center_gears (list): The list of gear names that center pays for
            providers (list): The provider links for the site
        """
        super(SiteSettings, self).__init__()

        self.created = datetime.datetime.now()
        """datetime: The creation time of this document"""

        self.modified = datetime.datetime.now()
        """datetime: The last modified time of this document"""

        self.center_gears = center_gears
        """list(str): The set of center-pays gears"""

        self.providers = providers
        """dict: The provider links for the site"""
