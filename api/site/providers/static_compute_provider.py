"""Provides the StaticComputeProvider class"""
from marshmallow import fields

from flywheel_common.providers.compute.base import BaseComputeProvider
from flywheel_common.providers.provider import BaseProviderSchema
from flywheel_common import errors


#class StaticComputeConfigSchema(Schema):
#    value = fields.String(required=True, allow_none=False, allow_blank=True)

class StaticComputeProviderSchema(BaseProviderSchema):
    """Schema definition for the object"""
    #config = fields.Nested(StaticComputeConfigSchema, required=True, many=False)
    config = fields.Dict(required=True, allow_none=True, allow_blank=True)
    creds = fields.Dict(required=False, allow_none=True, allow_blank=True)



# pylint: disable=too-few-public-methods
class StaticComputeProvider(BaseComputeProvider):
    """The static compute provider object."""

    _schema = StaticComputeProviderSchema()

    def validate(self):
        # Only empty configuration is valid
        if self.config:
            raise errors.ValidationError('Static Compute should have NO configuration!')

    def get_redacted_config(self):
        # There is no configuration, always return empty
        return {}

    def validate_permissions(self):
        return true
