import time

from .. import code_generator, mappers, models
from ... import config
from ...auth import require_admin, require_login
from ...validators import validate_data
from ...web import base, errors

RETRY_CODE_GENERATION_TILL = 5  # try to generate new codes for N seconds, if the previous generated code already exists


class MasterSubjectCodeHandler(base.RequestHandler):
    """Master subject code handler."""
    # pylint: disable=protected-access

    def __init__(self, *args, **kwargs):
        self.mapper = mappers.MasterSubjectCodes()
        super(MasterSubjectCodeHandler, self).__init__(*args, **kwargs)


    @require_login
    def verify_code(self, _id):
        """Verify that the given msc code exists."""
        master_code = self.mapper.get_by_id(_id)
        if not master_code:
            raise errors.APINotFoundException("This master subject code doesn't exists")

    @require_admin
    def post(self):
        """Generate or find master subject code for the given patient."""
        payload = self.request.json_body
        validate_data(payload, 'master-subject-code.json', 'input', 'POST')
        use_patient_id = payload.pop('use_patient_id')

        # grab config variables
        code_length = int(config.get_item('master_subject_code', 'size'))
        code_allowed_chars = config.get_item('master_subject_code', 'chars')
        code_prefix = config.get_item('master_subject_code', 'prefix')

        if payload.get('first_name') and payload.get('last_name'):
            # normalize first name, last name
            for k in ['first_name', 'last_name']:
                payload[k] = payload[k].strip().lower()

        start = time.time()
        while True:
            if use_patient_id:
                found_subj_codes = self.mapper.find(patient_id=payload['patient_id'])
            else:
                found_subj_codes = self.mapper.find(
                    first_name=payload['first_name'],
                    last_name=payload['last_name'],
                    date_of_birth=payload['date_of_birth']
                )
            found_subj_codes = list(found_subj_codes)

            if len(found_subj_codes) > 1:
                raise errors.InputValidationException(
                    'Found multiple master subject codes. '
                    'Use `patient_id` and set `use_patient_id` to true in the payload '
                    'to uniquely identify the subject.')
            elif found_subj_codes:
                # Update master subject code with new information
                subj_code = found_subj_codes[0]
                subj_code.set_missing_fields(**payload)
                update_payload = subj_code.to_dict()
                update_payload.pop('_id')
                self.mapper.update(subj_code._id, **update_payload)
                return {'code': subj_code._id}
            else:
                try:
                    # generate new master subject code
                    new_subj_code = code_generator.generate_code(
                        length=code_length,
                        allowed_chars=code_allowed_chars,
                        prefix=code_prefix
                    )
                    master_subject_code = models.MasterSubjectCode(new_subj_code, **payload)
                    self.mapper.insert(master_subject_code)
                    return {'code': master_subject_code._id}
                except errors.APIConflictException:
                    # Stop generating new codes after RETRY_CODE_GENERATION_TILL seconds to avoid timeout
                    if time.time() - start > RETRY_CODE_GENERATION_TILL:
                        self.log.critical(
                            "Couldn't generate new master subject code in {} second(s). "
                            "Possibly we are running out of the free ones. Consider increasing the size of the code.".format(time.time() - start)
                        )
                        raise
