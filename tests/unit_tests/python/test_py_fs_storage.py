import hashlib
import uuid

from flywheel_common import storage

def test_py_fs_storage():
    pyfs = storage.create_flywheel_fs(u'osfs:///tmp')
    assert pyfs._fs is not None
    assert pyfs.is_signed_url() == False

    f = pyfs.open(None, u'test.txt', 'w')
    assert f is not None

    f.write(u'This is a test')
    f.close()
    f = pyfs.open(None, u'test.txt', 'r')
    d = f.read()
    assert d == 'This is a test'
    d = f.close()


    f = pyfs.open(None, u'test.txt', 'w')
    assert f is not None
    f.write(u'Overwrite an existing file')
    f.close()
    f = pyfs.open(None, u'test.txt', 'r')
    d = f.read()
    assert d == 'Overwrite an existing file'
    d = f.close()


    f = pyfs.open(None, u'newdir/test.txt', 'w')
    assert f is not None
    f.write(u'Test in a new directory')
    f.close()
    f = pyfs.open(None, u'newdir/test.txt', 'r')
    d = f.read()
    assert d == 'Test in a new directory'
    d = f.close()


    f = pyfs.open(None, u'newdir/test2.txt', 'w')
    assert f is not None
    f.write(u'Test in an existing directory')
    f.close()
    f = pyfs.open(None, u'newdir/test2.txt', 'r')
    d = f.read()
    assert d == 'Test in an existing directory'
    d = f.close()


    f = pyfs.open(None, u'newdir/nested/test.txt', 'w')
    assert f is not None
    f.write(u'Test in a new nested directory')
    f.close()
    f = pyfs.open(None, u'newdir/nested/test.txt', 'r')
    d = f.read()
    assert d == 'Test in a new nested directory'
    d = f.close()


    f = pyfs.open(None, u'new_nested/nested/test.txt', 'w')
    assert f is not None
    f.write(u'Test in a new deeply nested directory')
    f.close()
    f = pyfs.open(None, u'new_nested/nested/test.txt', 'r')
    d = f.read()
    assert d == 'Test in a new deeply nested directory'
    d = f.close()


    # Test filesize
    data = pyfs.get_file_info(None, u'test.txt')
    assert 'filesize' in data


    # Test hashing of uploaded files.
    hash_alg = pyfs._default_hash_alg
    hasher = hashlib.new(hash_alg)
    hasher.update(u'Test in a new deeply nested directory')
    hash_val = hasher.hexdigest()
    hash_val = storage.format_hash(hash_alg, hash_val)

    assert hash_val == pyfs.get_file_hash(None, u'new_nested/nested/test.txt')

def test_pyfs_directory_selection():
    pyfs = storage.create_flywheel_fs(u'osfs:///tmp')

    #verify the file path is the uuid path
    uuid_ = unicode(str(uuid.uuid4))
    f = pyfs.open(uuid_, None, 'w')
    f.write(u'This is a test')
    f.close()
    f = pyfs.open(uuid_, None, 'r')
    f1 = pyfs.get_fs().open(storage.util.path_from_uuid(uuid_))
    assert f1 is not None
    assert f1.read() == f.read()
    f1.close()
    f.close()

    #verify the file path is the path hint
    f = pyfs.open(None, u'test/file/path.txt', 'w')
    f.write(u'This is a nested test')
    f.close()
    f = pyfs.open(None, u'test/file/path.txt', 'r')
    f1 = pyfs.get_fs().open(u'test/file/path.txt')
    assert f1 is not None
    assert f1.read() == f.read()
    f1.close()
    f.close()

    #Verify path hint takes precedence over uuid for legacy files
    f = pyfs.open(uuid_, u'test/file/path.txt', 'r')
    assert f.read() == u'This is a nested test'
    f.close()
