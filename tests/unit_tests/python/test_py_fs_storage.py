import hashlib
import uuid
import os

from flywheel_common import storage

def test_py_fs_storage():
    pyfs = storage.create_flywheel_fs(u'osfs:///tmp')
    assert pyfs._fs is not None
    assert pyfs.is_signed_url() == False

    file_id = str(uuid.uuid4())
    f = pyfs.open(file_id, 'w')
    assert f is not None

    f.write(u'This is a test')
    f.close()
    f = pyfs.open(file_id, 'r')
    d = f.read()
    assert d == 'This is a test'
    d = f.close()


    f = pyfs.open(file_id, 'w')
    assert f is not None
    f.write(u'Overwrite an existing file')
    f.close()
    f = pyfs.open(file_id, 'r')
    d = f.read()
    assert d == 'Overwrite an existing file'
    d = f.close()


    #It will be a new directory as long as the first 2 characters are different
    file_id2 = str(uuid.uuid4())
    while file_id[:2] == file_id2[:2]:
        file_id2 = str(uuid.uuid4())
    f = pyfs.open(file_id2, 'w')
    assert f is not None
    f.write(u'Test in a new directory')
    f.close()
    f = pyfs.open(file_id2, 'r')
    d = f.read()
    assert d == 'Test in a new directory'
    d = f.close()


    # Test filesize
    data = pyfs.get_file_info(file_id)
    assert 'filesize' in data


    # Test hashing of uploaded files.
    hash_alg = pyfs._default_hash_alg
    hasher = hashlib.new(hash_alg)
    hasher.update(u'Overwrite an existing file')
    hash_val = hasher.hexdigest()
    hash_val = storage.format_hash(hash_alg, hash_val)

    assert hash_val == pyfs.get_file_hash(file_id)

    # Test opening based on hash value.
    # We create a file on the local fs that would be in the same spot CAS files would have been
    # We have to be sure to write the same contents so the hash will be the same
    path = pyfs.path_from_hash(hash_val)
    dirname = os.path.dirname(path)
    if not pyfs.get_fs().isdir(unicode(dirname)):
        pyfs.get_fs().makedirs(unicode(dirname))
    f = pyfs.get_fs().open(unicode(path), u'w')
    f.write(u'Overwrite an existing file')
    f.close()

    f = pyfs.open(None, u'r', hash_val)
    assert f is not None
    d = f.read()
    assert d == 'Overwrite an existing file'

