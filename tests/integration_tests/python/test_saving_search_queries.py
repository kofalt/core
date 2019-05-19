
def test_saving_search_queries(as_admin, data_builder, as_user):
    group = data_builder.create_group()
    project = data_builder.create_project(public=False)

    # Try posting a malformed search
    r = as_admin.post('/dataexplorer/queries', json={"not-label":"random-string"})
    assert r.status_code == 400

    # Try getting a non-existent saved search
    r = as_admin.get('/dataexplorer/queries/000000000000000000000000')
    assert r.status_code == 404

    # Save a search
    r = as_admin.post('/dataexplorer/queries', json={
        'label': 'search1',
        'search': {'return_type': 'session'},
        'parent': {'type': 'project', 'id': project}
    })
    assert r.ok
    search = r.json()['_id']

    # Get all searches admin has access to
    r = as_admin.get('/dataexplorer/queries')
    assert r.ok
    assert len(r.json()) == 1
    assert r.json()[0]['label'] == 'search1'

    # Get all searches user has access to
    r = as_user.get('/dataexplorer/queries')
    assert r.ok
    assert r.json() == []

    # Get the saved search by id
    r = as_admin.get('/dataexplorer/queries/' + search)
    assert r.ok
    assert r.json()['label'] == 'search1'

    # Malformed search replace
    payload = {'label': 'good-label', 'search' : { 'not-return-type' : 'not-container'}}
    r = as_admin.put('/dataexplorer/queries/' + search, json=payload)
    assert r.status_code == 400

    # Replace search
    r = as_admin.get('/dataexplorer/queries/' + search)
    assert r.ok
    assert r.json()['label'] == 'search1'
    payload = {'label': 'newSearch'}
    r = as_admin.put('/dataexplorer/queries/' + search, json=payload)
    assert r.ok
    assert r.json()['modified'] == 1
    r = as_admin.get('/dataexplorer/queries/' + search)
    assert r.ok
    assert r.json()['label'] == 'newSearch'

    # Try to access the query without permissions
    r = as_user.get('/dataexplorer/queries/' + search)
    assert r.status_code == 403

    # Add permission to project
    r = as_admin.post('/projects/' + project + '/permissions', json={'access': 'ro', '_id': 'user@user.com'})
    assert r.ok

    # Get query as a user with permission
    r = as_user.get('/dataexplorer/queries/' + search)
    assert r.ok

    # Try to modify the search query
    payload = {'label': 'Users Search'}
    r = as_user.put('/dataexplorer/queries/' + search, json=payload)
    assert r.status_code == 403

    # Remove permission
    r = as_admin.delete('/projects/' + project + '/permissions/user@user.com')
    assert r.ok

    # Delete saved search
    r = as_admin.delete('/dataexplorer/queries/' + search)
    assert r.ok
    r = as_admin.get('/dataexplorer/queries')
    assert r.ok
    assert len(r.json()) == 0


def test_saving_site_search_queries(as_admin, data_builder, as_user, as_public):
    # Try saving a search as public
    r = as_user.post('/dataexplorer/queries', json={
        'label': 'search1',
        'search': {'return_type': 'session'},
        'parent': {'type': 'site', 'id': 'site'}
    })
    assert r.status_code == 403

    # Try saving a search as a user
    r = as_user.post('/dataexplorer/queries', json={
        'label': 'search1',
        'search': {'return_type': 'session'},
        'parent': {'type': 'site', 'id': 'site'}
    })
    assert r.status_code == 403

    # Save a search
    r = as_admin.post('/dataexplorer/queries', json={
        'label': 'search1',
        'search': {'return_type': 'session'},
        'parent': {'type': 'site', 'id': 'site'}
    })
    assert r.ok
    search = r.json()['_id']

    # Try to get all searches public has access to
    r = as_public.get('/dataexplorer/queries')
    assert r.status_code == 403

    # Get all searches user has access to
    r = as_user.get('/dataexplorer/queries')
    assert r.ok
    assert len(r.json()) == 0

    # Try to get query as public
    r = as_public.get('/dataexplorer/queries/' + search)
    assert r.status_code == 403

    # Try to get query as a user
    r = as_user.get('/dataexplorer/queries/' + search)
    assert r.status_code == 403

    # Get query as an admin
    r = as_admin.get('/dataexplorer/queries/' + search)
    assert r.ok

    # Try to delete as public
    r = as_public.delete('/dataexplorer/queries/' + search)
    assert r.status_code == 403

    # Try to delete as user
    r = as_user.delete('/dataexplorer/queries/' + search)
    assert r.status_code == 403

    # Delete as admin
    r = as_admin.delete('/dataexplorer/queries/' + search)
    assert r.ok

