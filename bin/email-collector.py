#!/usr/bin/env python
"""
Generate report from the user data.
"""

import argparse
import os
import sys
import re

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from fs import open_fs
import fs.path
import fs.copy

def main(argv=None):
    args = parse_args(argv or sys.argv[1:] or ['--help'])

    api_url = os.environ['SCITRAN_SITE_API_URL']
    api_shared_secret = os.environ['SCITRAN_CORE_DRONE_SECRET']
    user_list_file = os.environ['SCITRAN_SITE_URL']
    local_fs_path = "/var/scitran/code"

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Calculate the URL of the cloud storage
    chunks = re.split('://|\?', os.environ['SCITRAN_CENTRAL_FS_URL'])
    if chunks[0] == 'osfs':
        print ("Remote backup storage is not configured")
        sys.exit()
    cloud_fs_url = chunks[0] + "://" + chunks[1] + "/email-collector" + ("?" + chunks[2] if len(chunks)>=3 else '')

    # Get list of users
    api = API(api_url, args.api_shared_secret)
    users = api.get('/users')
    assert users.ok
    
    # Save the user list into the cloud
    cloud_fs = open_fs(cloud_fs_url)
    payload = unicode(str(api.get('/users').json()), "utf-8")
    f = cloud_fs.open(unicode(user_list_file, "utf-8"), 'w+')
    f.write(payload)
    f.close()

    #for path in cloud_fs.walk.files(filter=['*']):
    #    print('path: ', path)

    cloud_fs.close()


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', required=True, help='url to scitran/core api')
    parser.add_argument('--api-shared-secret', required=True, help='shared secret for scitran/core api')
    return parser.parse_args(argv)


class API(requests.Session):
    def __init__(self, base_url, secret):
        super(API, self).__init__()
        self.verify = False
        self.base_url = base_url
        self.headers.update({'X-SciTran-Auth': secret,
                             'X-SciTran-Method': 'prometheus',
                             'X-SciTran-Name': 'flywheel-utility'})

    def request(self, method, url, **kwargs):
        return super(API, self).request(method, self.base_url + url, **kwargs)


if __name__ == '__main__':
    main()