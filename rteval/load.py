#!/usr/bin/python -tt
#
#   Copyright 2009   Clark Williams <williams@redhat.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#
#   For the avoidance of doubt the "preferred form" of this code is one which
#   is in an open unpatent encumbered format. Where cryptographic key signing
#   forms part of the process of creating an executable the information
#   including keys needed to generate an equivalently functional executable
#   are deemed to be part of the source code.
#

import sys
import os
import os.path
import time
import subprocess
import threading

class Load(threading.Thread):
    def __init__(self, name="<unnamed>", source=None, dir=None, 
                 debug=False, num_cpus=1):
        threading.Thread.__init__(self)
        self.name = name
        self.source = source	# abs path to source archive
        self.dir = dir		# abs path to run dir
        self.mydir = None
        self.startevent = threading.Event()
        self.stopevent = threading.Event()
        self.ready = False
        self.debugging = debug
        self.num_cpus = num_cpus

        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def debug(self, str):
        if self.debugging: print str

    def isReady(self):
        return self.ready

    def setup(self, topdir, tarball):
        pass

    def build(self, dir):
        pass

    def runload(self, dir):
        pass

    def run(self):
        if self.stopevent.isSet():
            return
        self.setup()
        if self.stopevent.isSet():
            return
        self.build()
        while True:
            if self.stopevent.isSet():
                return
            self.startevent.wait(1.0)
            if self.startevent.isSet():
                break
        self.runload()

    def report(self):
        pass

    def genxml(self, x):
        pass
