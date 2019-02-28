import hashlib

from api.util import format_hash
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
