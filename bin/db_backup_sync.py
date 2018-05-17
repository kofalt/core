from __future__ import print_function
import os
import sys
import re
from fs import open_fs
import fs.move
import fs.subfs
import fs.tempfs
import fs.path
import fs.errors
import fs.tree
import fs.copy

SCITRAN_PERSISTENT_FS_URL = os.environ['SCITRAN_PERSISTENT_FS_URL']
if not SCITRAN_PERSISTENT_FS_URL:
    print ("Remote backup storage is not configured")
    sys.exit()

chunks = re.split('://|\?', SCITRAN_PERSISTENT_FS_URL)

if chunks[0] == 'osfs':
    print ("Remote backup storage is not configured")
    sys.exit()

cloud_fs_url = chunks[0] + "://" + chunks[1] + "/db_backup" + ("?" + chunks[2] if len(chunks)>=3 else '')
local_fs_path = sys.argv[1]
print ("Synchronize:" + local_fs_path + " --> " + cloud_fs_url)

cloud_fs = open_fs(cloud_fs_url)
local_fs = open_fs(local_fs_path)

# 1.) Find a upload the new files into the cloud storage
try:
    fs.copy.copy_fs_if_newer(local_fs_path, cloud_fs, None, lambda src_fs, src_path, dst_fs, dst_path : print ("Upload: " + src_path))
except ValueError:
    print ("Synchronization error: " + ValueError)

# 2.) Delete files from the cloud storage that does not exist on the
#     local file system any more.
for path in cloud_fs.walk.files(filter=['*']):
    if not local_fs.exists(path):
        print("Cleanup: " + path)
        try:
            cloud_fs.remove(path)
        except ValueError:
            print ("Synchronization error: " + ValueError)

cloud_fs.close()
local_fs.close()
