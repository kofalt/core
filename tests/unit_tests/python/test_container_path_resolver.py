import bson
from api.data_export.strategy.container_path_resolver import ContainerPathResolver

def test_container_path_resolver_path_prefix():
    project_id = bson.ObjectId()
    subject_id = bson.ObjectId()

    containers = {
        'group': {
            '_id': 'group_1',
            'label': 'group_1'
        },
        'project': {
            '_id': project_id,
            'label': 'project_1',
        },
        'subject': {
            '_id': subject_id,
            'label': '1001'
        }
    }

    resolver = ContainerPathResolver()
    path = resolver.get_path(containers, 'subject', subject_id)
    assert path == ('group_1', 'project_1', '1001')

    resolver = ContainerPathResolver(path_prefix='test')
    path = resolver.get_path(containers, 'subject', subject_id)
    assert path == ('test', 'group_1', 'project_1', '1001')

    resolver = ContainerPathResolver(path_prefix=('flywheel', 'test'))
    path = resolver.get_path(containers, 'subject', subject_id)
    assert path == ('flywheel', 'test', 'group_1', 'project_1', '1001')

def test_container_path_resolver_include_group():
    project_id = bson.ObjectId()
    subject_id = bson.ObjectId()

    containers = {
        'group': {
            '_id': 'group_1',
            'label': 'group_1'
        },
        'project': {
            '_id': project_id,
            'label': 'project_1',
        },
        'subject': {
            '_id': subject_id,
            'label': '1001'
        }
    }

    resolver = ContainerPathResolver()
    path = resolver.get_path(containers, 'subject', subject_id)
    assert path == ('group_1', 'project_1', '1001')

    resolver = ContainerPathResolver(include_group=False)
    path = resolver.get_path(containers, 'subject', subject_id)
    assert path == ('project_1', '1001')

def test_container_path_resolver_analyses():
    project_id = bson.ObjectId()
    subject_id = bson.ObjectId()
    analysis_id = bson.ObjectId()

    containers = {
        'group': {
            '_id': 'group_1',
            'label': 'group_1'
        },
        'project': {
            '_id': project_id,
            'label': 'project_1',
        },
        'subject': {
            '_id': subject_id,
            'label': '1001'
        },
        'analysis': {
            '_id': analysis_id,
            'label': 'analysis_label',
            'parent': {
                'type': 'project',
                'id': project_id
            }
        }
    }

    resolver = ContainerPathResolver()
    path = resolver.get_path(containers, 'analysis', analysis_id)
    assert path == ('group_1', 'project_1', 'analysis_label')

    # Change parent
    containers['analysis']['parent'] = {'type': 'subject', 'id': subject_id}

    resolver = ContainerPathResolver()
    path = resolver.get_path(containers, 'analysis', analysis_id)
    assert path == ('group_1', 'project_1', '1001', 'analysis_label')

def test_container_path_resolver_prefix_containers():
    project_id = bson.ObjectId()
    subject_id = bson.ObjectId()
    session_id = bson.ObjectId()
    acquisition_id = bson.ObjectId()
    analysis_id = bson.ObjectId()

    containers = {
        'project': {
            '_id': project_id,
            'label': 'project_1',
        },
        'subject': {
            '_id': subject_id,
            'label': '1001'
        },
        'session': {
            '_id': session_id,
            'label': 'ses-01'
        },
        'acquisition': {
            '_id': acquisition_id,
            'label': 'SCAN'
        },
        'analysis': {
            '_id': analysis_id,
            'label': 'AFQ 2018-01-13',
            'parent': {
                'type': 'project',
                'id': project_id
            }
        }
    }

    resolver = ContainerPathResolver(include_group=False, prefix_containers=True)
    path = resolver.get_path(containers, 'project', project_id)
    assert path == ('project_1',)

    path = resolver.get_path(containers, 'subject', subject_id)
    assert path == ('project_1', 'SUBJECTS', '1001')

    path = resolver.get_path(containers, 'acquisition', acquisition_id)
    assert path == ('project_1', 'SUBJECTS', '1001', 'SESSIONS', 'ses-01', 'ACQUISITIONS', 'SCAN')

    path = resolver.get_path(containers, 'analysis', analysis_id)
    assert path == ('project_1', 'ANALYSES', 'AFQ 2018-01-13')

    # Change parent
    containers['analysis']['parent'] = {'type': 'acquisition', 'id': acquisition_id}
    resolver = ContainerPathResolver(include_group=False, prefix_containers=True)
    path = resolver.get_path(containers, 'analysis', analysis_id)
    assert path == ('project_1', 'SUBJECTS', '1001', 'SESSIONS', 'ses-01',
        'ACQUISITIONS', 'SCAN', 'ANALYSES', 'AFQ 2018-01-13')
