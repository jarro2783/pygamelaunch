#!/usr/bin/python3 -O

"""
This is an executable that runs the pygamelaunch launcher.
"""

import launcher
import sys
import traceback

try:
    launcher.main()
# pylint: disable=bare-except
except:
    traceback.print_exc(file=sys.stderr)
    print("Oops! It looks like pygamelaunch has died.")
    print("Please report the above output at " +
          "github.com/jarro2783/pygamelaunch")
    
