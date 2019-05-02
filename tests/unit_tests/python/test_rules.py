import pytest
import pymongo
import bson

from api.jobs import rules, models, mappers
from api.web import errors

# Statefully holds onto some construction args and can return tuples to unroll for calling rules.eval_match.
# Might indicate a need for a match tuple in rules.py.
class rulePart:
    # Hold onto some param state
    def __init__(self, match_type=None, match_param=None, file_=None, container=None, regex=None):
        self.match_type  = match_type
        self.match_param = match_param
        self.file_       = file_
        self.container   = container
        self.regex       = regex

    # Return params as tuple, optionally with some modifications
    def gen(self, match_type=None, match_param=None, file_=None, container=None, regex=None):

        return (
            match_type  if match_type  is not None else self.match_type,
            match_param if match_param is not None else self.match_param,
            file_       if file_       is not None else self.file_,
            container   if container   is not None else self.container,
            regex       if regex       is not None else self.regex,
        )

# DISCUSS: this basically asserts that the log helper doesn't throw, which is of non-zero but questionable value.
# Could instead be marked for pytest et. al to ignore coverage? Desirability? Compatibility?
def test_log_file_key_error():
    rules._log_file_key_error({'name': 'wat'}, {'_id': 0}, 'example')


def test_eval_match_file_type():
    part = rulePart(match_type='file.type', match_param='dicom')

    args = part.gen(file_={'type': 'dicom' })
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(file_={'type': 'nifti' })
    result = rules.eval_match(*args)
    assert result == False

    # Check match returns false without raising when not given a file.type
    args = part.gen(file_={'a': 'b'}, container={'a': 'b'})
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_file_type_regex():
    part = rulePart(match_type='file.type', file_={'type': 'dicom'}, regex=True)

    args = part.gen(match_param='DiC[o]{1}M$')
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(match_param='DiC[o]{2}M$')
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_file_name_match_exact():
    part = rulePart(match_type='file.name', match_param='file.txt')

    args = part.gen(file_={'name': 'file.txt' })
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(file_={'name': 'file2.txt' })
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_file_name_match_relative():
    part = rulePart(match_type='file.name', match_param='*.txt')

    args = part.gen(file_={'name': 'file.txt' })
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(file_={'name': 'file.log' })
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_file_name_match_regex():
    part = rulePart(match_type='file.name', file_={'name': 'test.dicom.zip'}, regex=True)

    args = part.gen(match_param='.*DiC[o]{1}M\.zip$')
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(match_param='.*DiC[o]{2}M\.zip$')
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_file_classification():
    part = rulePart(match_type='file.classification', file_={'classification': {'intent': ['a', 'diffusion', 'b'] }})

    args = part.gen(match_param='diffusion')
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(match_param='c')
    result = rules.eval_match(*args)
    assert result == False

    # Check match returns false without raising when not given a file.classification
    args = part.gen(match_param='', file_={'a': 'b'}, container={'a': 'b'})
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_file_classification_regex():
    part = rulePart(match_type='file.classification', file_={'classification': {'intent': ['diffusion']}}, regex=True)

    args = part.gen(match_param='test|diffusion')
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(match_param='test|foo')
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_container_has_type():
    part = rulePart(match_type='container.has-type', container={'files': [
            {'type': 'diffusion'},
            {'type': 'other'},
        ]})

    args = part.gen(match_param='other')
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(match_param='d')
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_container_has_type_regex():
    part = rulePart(match_type='container.has-type', regex=True, container={'files': [
        {'type': 'diffusion'},
        {'type': 'other'},
    ]})

    args = part.gen(match_param='test|diffusion')
    result = rules.eval_match(*args)
    assert result == True

    args = part.gen(match_param='test|foo')
    result = rules.eval_match(*args)
    assert result == False

def test_eval_match_unknown_type():
    with pytest.raises(Exception):
        rules.eval_match('does-not-exist', None, None, None)


def test_eval_rule_any():
    container = {'a': 'b'}

    rule_doc = {
        'project_id': '000000000000000000000000',
        'name': 'test_eval_rule_any',
        'any': [
            {
                'type': 'file.type',
                'value': 'dicom'
            },
            {
                'type': 'file.name',
                'value': '*.dcm',
            },
        ],
        'all': [],
        'not': [],
        'gear_id': '000000000000000000000000',
    }
    rule = models.Rule.from_dict(rule_doc)

    file_ = {'name': 'hello.dcm', 'type': 'a'}
    result = rules.eval_rule(rule, file_, container)
    assert result == True

    file_ = {'name': 'hello.txt', 'type': 'dicom'}
    result = rules.eval_rule(rule, file_, container)
    assert result == True

    file_ = {'name': 'hello.dcm', 'type': 'dicom'}
    result = rules.eval_rule(rule, file_, container)
    assert result == True

    file_ = {'name': 'hello.txt', 'type': 'a'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

def test_eval_rule_all():
    container = {'a': 'b'}

    rule_doc = {
        'project_id': '000000000000000000000000',
        'name': 'test_eval_rule_any',
        'any': [],
        'not': [],
        'all': [
            {
                'type': 'file.type',
                'value': 'dicom'
            },
            {
                'type': 'file.name',
                'value': '*.dcm',
            },
        ],
        'gear_id': '000000000000000000000000',
    }
    rule = models.Rule.from_dict(rule_doc)

    file_ = {'name': 'hello.dcm', 'type': 'a'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.txt', 'type': 'dicom'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.dcm', 'type': 'dicom'}
    result = rules.eval_rule(rule, file_, container)
    assert result == True

    file_ = {'name': 'hello.txt', 'type': 'a'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

def test_eval_rule_not():
    container = {'a': 'b'}

    rule_doc = {
        'project_id': '000000000000000000000000',
        'name': 'test_eval_rule_any',
        'not': [
            {
                'type': 'file.classification',
                'value': 'non-image'
            },
            {
                'type': 'file.name',
                'value': '*.dcm',
            },
            {
                'type': 'file.classification',
                'value': 'functional'
            }
        ],
        'all': [],
        'any': [],
        'gear_id': '000000000000000000000000',
    }
    rule = models.Rule.from_dict(rule_doc)

    file_ = {'name': 'hello.dcm', 'type': 'a', 'classification': {'Custom': ['b']}}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.txt', 'type': 'a', 'classification': {'Custom': ['non-image']}}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.txt', 'type': 'a', 'classification': {'Custom': ['Functional']}}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.txt'}
    result = rules.eval_rule(rule, file_, container)
    assert result == True


def test_eval_rule_any_all_not():
    container = {'a': 'b'}

    rule_doc = {
        'project_id': '000000000000000000000000',
        'name': 'test_eval_rule_any',
        'any': [
            {
                'type': 'file.type',
                'value': 'dicom'
            },
            {
                'type': 'file.name',
                'value': '*.dcm',
            },
        ],
        'all': [
            {
                'type': 'file.type',
                'value': 'dicom'
            },
            {
                'type': 'file.name',
                'value': '*.dcm',
            },
        ],
        'not': [
            {
                'type': 'file.classification',
                'value': 'non-image'
            }
        ],
        'gear_id': '000000000000000000000000',
    }
    rule = models.Rule.from_dict(rule_doc)

    file_ = {'name': 'hello.dcm', 'type': 'a'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.txt', 'type': 'dicom'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.dcm', 'type': 'dicom'}
    result = rules.eval_rule(rule, file_, container)
    assert result == True

    file_ = {'name': 'hello.dcm', 'type': 'dicom', 'classification': {'Custom': ['Non-Image', 'Something Else']}}
    result = rules.eval_rule(rule, file_, container)
    assert result == False

    file_ = {'name': 'hello.txt', 'type': 'a'}
    result = rules.eval_rule(rule, file_, container)
    assert result == False


def test_rule_model_dict_methods():
    test_rule = models.Rule('gear_id', 'rule_name', [{'file.type': 'dicom'}],
                           [], [])
    assert getattr(test_rule, 'any', None) is None
    assert test_rule.any_ == [{'file.type': 'dicom'}]

    test_rule_dict = test_rule.to_dict()
    assert test_rule_dict.get('any_') is None
    assert test_rule_dict.get('any') == test_rule.any_

    translated_test_rule = models.Rule.from_dict(test_rule_dict)
    assert getattr(translated_test_rule, 'any', None) is None
    assert translated_test_rule.any_ == [{'file.type': 'dicom'}]

    assert test_rule == translated_test_rule


def test_rule_model_copy():
    test_rule = models.Rule('gear_id', 'rule_name', [], [], [])
    test_rule.rule_id = 'Hello'

    copy_test_rule = test_rule.copy()

    test_rule_dict = test_rule.to_dict()
    test_rule_dict.pop('_id')
    copy_test_rule_dict = copy_test_rule.to_dict()

    assert test_rule_dict == copy_test_rule_dict


def test_rules_mapper_insert_rule(api_db):
    # Insert Rule
    rules_mapper = mappers.RulesMapper(db=api_db)
    rule = models.Rule('gear_id', 'insert_rule', [], [], [])

    rule_id = rules_mapper.insert(rule)
    assert rule.rule_id == rule_id

    rule_mongo_document = api_db.project_rules.find_one({'_id': rule_id})
    assert rule_mongo_document == rule.to_dict()

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_id})


def test_rules_mapper_duplicate_insert_rule(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)
    rule = models.Rule('gear_id', 'insert_rule', [], [], [])
    rules_mapper.insert(rule)

    # Try to insert it again
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        rules_mapper.insert(rule)

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule.rule_id})


def test_rules_mapper_insert_preset_id_rule(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)
    rule = models.Rule('gear_id', 'insert_rule', [], [], [])

    # Insert a rule with an id already set
    rule.rule_id = 'preset_id_rule_id'
    rule_id = rules_mapper.insert(rule)

    assert rule_id == 'preset_id_rule_id'
    assert rule_id == rule.rule_id

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_id})


def test_rules_mapper_insert_copy_rule(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)
    rule = models.Rule('gear_id', 'insert_rule', [], [], [])
    rules_mapper.insert(rule)

    # Insert a rule copy
    copy_rule_id = rules_mapper.insert(rule.copy())
    assert copy_rule_id != rule.rule_id

    copy_rule_mongo_document = api_db.project_rules.find_one(
        {'_id': copy_rule_id}
    )
    assert copy_rule_mongo_document

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule.rule_id})
    api_db.project_rules.delete_one({'_id': copy_rule_id})


def test_rules_mapper_get_rule(api_db):
    # Add rules to db
    rule_1_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'site'
    }).inserted_id
    rule_2_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'project_id'
    }).inserted_id

    rules_mapper = mappers.RulesMapper(db=api_db)

    # Find a single rule by id
    rule_1 = rules_mapper.get(rule_1_id)
    assert isinstance(rule_1, models.Rule)
    assert rule_1.rule_id == rule_1_id

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_1_id})
    api_db.project_rules.delete_one({'_id': rule_2_id})


def test_rules_mapper_get_rule(api_db):
    # Add rules to db
    rule_1_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'not': None,
        'project_id': 'site'
    }).inserted_id

    rules_mapper = mappers.RulesMapper(db=api_db)

    # Find a single rule by id
    rule_1 = rules_mapper.get(rule_1_id)
    assert isinstance(rule_1, models.Rule)
    assert rule_1.rule_id == rule_1_id

    # Make sure all rule eval values are lists
    assert isinstance(rule_1.not_, list)
    assert isinstance(rule_1.all_, list)
    assert isinstance(rule_1.any_, list)

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_1_id})


def test_rules_mapper_get_rule_that_does_not_exist(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)

    # Look for rule that doesn't exist
    rule = rules_mapper.get(bson.ObjectId())
    assert rule is None


def test_rules_mapper_get_rule_projection(api_db):
    # Add rules to db
    rule_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'config': {'key': 'value'},
        'project_id': 'site'
    }).inserted_id

    rules_mapper = mappers.RulesMapper(db=api_db)

    # Find a single rule without a projection
    rule = rules_mapper.get(rule_id)
    assert rule.config['key'] == 'value'

    # Find a single rule by id with a projection
    rule_projected = rules_mapper.get(rule_id, projection={'config': 0})
    assert rule_projected.config is None

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_id})


def test_rules_mapper_find_all(api_db):
    # Add rules to db
    rule_1_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'site'
    }).inserted_id
    rule_2_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'project_id'
    }).inserted_id
    rule_3_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'project_id'
    }).inserted_id

    rules_mapper = mappers.RulesMapper(db=api_db)

    # Find all rules
    rules = rules_mapper.find_all()
    rules = list(rules)

    assert len(rules) == 3
    assert isinstance(rules[0], models.Rule)

    rule_ids = [rule.rule_id for rule in rules]
    assert rule_1_id in rule_ids
    assert rule_2_id in rule_ids
    assert rule_3_id in rule_ids

    # Clean Up
    for rule_id in rule_ids:
        api_db.project_rules.delete_one({'_id': rule_id})


def test_rules_mapper_find_all_with_query(api_db):
    # Add rules to db
    rule_1_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'site'
    }).inserted_id
    rule_2_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'project_id'
    }).inserted_id
    rule_3_id = api_db.project_rules.insert_one({
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'project_id': 'project_id'
    }).inserted_id

    rules_mapper = mappers.RulesMapper(db=api_db)

    # Find all rules for project project_id
    rules = rules_mapper.find_all(project_id='project_id')
    rules = list(rules)

    assert len(rules) == 2
    assert isinstance(rules[0], models.Rule)

    for rule in rules:
        assert rule.project_id == 'project_id'

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_1_id})
    api_db.project_rules.delete_one({'_id': rule_2_id})
    api_db.project_rules.delete_one({'_id': rule_3_id})


def test_rules_mapper_find_all_when_no_rules_exist(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)
    rules = list(rules_mapper.find_all())
    assert rules == []


def test_rules_mapper_patch_rule(api_db):
    # Add rules to db
    rule_doc = {
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'config': {'key': 'value'},
        'project_id': 'site'
    }
    rule_id = api_db.project_rules.insert_one(rule_doc).inserted_id
    rules_mapper = mappers.RulesMapper(db=api_db)

    # Patch rule name
    rules_mapper.patch(rule_id, {'name': 'new_rule_name'})

    patched_rule_doc = api_db.project_rules.find_one({'_id': rule_id})
    assert patched_rule_doc['name'] == 'new_rule_name'

    # Clean Up
    api_db.project_rules.delete_one({'_id': rule_id})


def test_rules_mapper_patch_rule_that_does_not_exist(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)

    with pytest.raises(errors.APINotFoundException):
        rules_mapper.patch(bson.ObjectId(), {'name': 'new_rule_name'})


def test_rules_mapper_delete_rule(api_db):
    # Add rules to db
    rule_doc = {
        'gear_id': 'gear_id',
        'name': 'rule_name',
        'any': [],
        'all': [],
        'not': [],
        'config': {'key': 'value'},
        'project_id': 'site'
    }
    rule_id = api_db.project_rules.insert_one(rule_doc).inserted_id
    rules_mapper = mappers.RulesMapper(db=api_db)

    deleted_count = rules_mapper.delete(rule_id)
    assert deleted_count == 1

    rule = api_db.project_rules.find_one({'_id': rule_id})
    assert rule is None


def test_rules_mapper_delete_rule_that_does_not_exist(api_db):
    rules_mapper = mappers.RulesMapper(db=api_db)

    deleted_count = rules_mapper.delete(bson.ObjectId())
    assert deleted_count == 0

