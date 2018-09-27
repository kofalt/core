#!/usr/bin/env python
import os
import sys

bin_path = os.path.dirname(os.path.dirname(__file__))
sys.path.append(bin_path)

import database

database.upgrade_to_55(dry_run=True)
