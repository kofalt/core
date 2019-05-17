"""Master subject code model."""

from ... import models


class MasterSubjectCode(models.Base):
    """Master subject code data model."""

    def __init__(self, _id, patient_id=None, first_name=None, last_name=None, date_of_birth=None):
        super(MasterSubjectCode, self).__init__()

        self._id = _id
        self.patient_id = patient_id
        self.first_name = first_name
        self.last_name = last_name
        self.date_of_birth = date_of_birth

    def set_missing_fields(self, **kwargs):
        """Set the given fields if None

        Arguments:
            **kwargs -- Fields to set
        """

        for key in kwargs.keys():
            if self.get(key) is None:
                self[key] = kwargs[key]
