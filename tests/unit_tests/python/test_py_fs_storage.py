from api.storage.py_fs_storage import PyFsStorage

def test_py_fs_storage():
    storage = PyFsStorage(u'osfs:///tmp')
    assert storage._fs is not None
    assert storage.is_signed_url() == False

    f = storage.open(None, u'test.txt', 'w', None)
    assert f is not None

    f.write(u'This is a test')
    f.close()
    f = storage.open(None, u'test.txt', 'r', None)
    d = f.read()
    assert d == 'This is a test'
    d = f.close()


    f = storage.open(None, u'test.txt', 'w', None)
    assert f is not None
    f.write(u'Overwrite an existing file')
    f.close()
    f = storage.open(None, u'test.txt', 'r', None)
    d = f.read()
    assert d == 'Overwrite an existing file'
    d = f.close()
    

    f = storage.open(None, u'newdir/test.txt', 'w', None)
    assert f is not None
    f.write(u'Test in a new directory')
    f.close()
    f = storage.open(None, u'newdir/test.txt', 'r', None)
    d = f.read()
    assert d == 'Test in a new directory'
    d = f.close()


    f = storage.open(None, u'newdir/test2.txt', 'w', None)
    assert f is not None
    f.write(u'Test in an existing directory')
    f.close()
    f = storage.open(None, u'newdir/test2.txt', 'r', None)
    d = f.read()
    assert d == 'Test in an existing directory'
    d = f.close()


    f = storage.open(None, u'newdir/nested/test.txt', 'w', None)
    assert f is not None
    f.write(u'Test in a new nested directory')
    f.close()
    f = storage.open(None, u'newdir/nested/test.txt', 'r', None)
    d = f.read()
    assert d == 'Test in a new nested directory'
    d = f.close()
    
    
    f = storage.open(None, u'new_nested/nested/test.txt', 'w', None)
    assert f is not None
    f.write(u'Test in a new deeply nested directory')
    f.close()
    f = storage.open(None, u'new_nested/nested/test.txt', 'r', None)
    d = f.read()
    assert d == 'Test in a new deeply nested directory'
    d = f.close()

    data = storage.get_file_info(None, 'test.txt')
    assert filesize in data


