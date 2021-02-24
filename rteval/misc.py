#!/usr/bin/python3 -tt
#
# Copyright (C) 2015 Clark Williams <clark.williams@gmail.com>
# Copyright (C) 2015 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.


import os
import glob

# expand a string range into a list
# don't error check against online cpus
def expand_cpulist(cpulist):
    '''expand a range string into an array of cpu numbers'''
    result = []
    for part in cpulist.split(','):
        if '-' in part:
            a, b = part.split('-')
            a, b = int(a), int(b)
            result.extend(list(range(a, b + 1)))
        else:
            a = int(part)
            result.append(a)
    return [str(i) for i in list(set(result))]

def online_cpus():
    online_cpus = []
    # Check for the online file with cpu1 since cpu0 can't always be offlined
    if os.path.exists('/sys/devices/system/cpu/cpu1/online'):
        for c in glob.glob('/sys/devices/system/cpu/cpu[0-9]*'):
            num = str(c.replace('/sys/devices/system/cpu/cpu', ''))
            # On some machine you can't turn off cpu0
            if not os.path.exists(c + '/online') and num == "0":
                online_cpus.append(num)
            else:
                with open(c + '/online') as f:
                    is_online = f.read().rstrip('\n')
                if is_online == "1":
                    online_cpus.append(num)
    else: # use the old heuristic
        for c in glob.glob('/sys/devices/system/cpu/cpu[0-9]*'):
            num = str(c.replace('/sys/devices/system/cpu/cpu', ''))
            online_cpus.append(num)
    return online_cpus

def invert_cpulist(cpulist):
    return [c for c in online_cpus() if c not in cpulist]

def compress_cpulist(cpulist):
    if isinstance(cpulist[0], int):
        return ",".join(str(e) for e in cpulist)
    return ",".join(cpulist)

def cpuinfo():
    core = -1
    info = {}
    for l in open('/proc/cpuinfo'):
        l = l.strip()
        if not l:
            continue
        # Split a maximum of one time. In case a model name has ':' in it
        key, val = [i.strip() for i in l.split(':', 1)]
        if key == 'processor':
            core = val
            info[core] = {}
            continue
        info[core][key] = val
    return info

# Pass the per-core dictionary that is part of the dictionary returned
# by cpuinfo()
def get_cpumodel(core_info):
    desc = core_info.get('model name', '')
    if not desc:
        # On Arm (both 32 and 64 bit), 'CPU Implementer' is always
        # present. Return 'unknown' otherwise
        if 'CPU implementer' not in core_info:
            desc = 'unknown'
        else:
            implementor = core_info.get('CPU implementer', '')
            architecture = core_info.get('CPU architecture', '')
            variant = core_info.get('CPU variant', '')
            part = core_info.get('CPU part', '')
            revision = core_info.get('CPU revision', '')

            desc = 'Implementor: %s Architecture: %s Variant: %s Part: %s Revision: %s' \
                % (implementor, architecture, variant, part, revision)

    return desc

if __name__ == "__main__":

    info = cpuinfo()
    idx = sorted(info.keys())
    for i in idx:
        print("%s: %s" % (i, info[i]))

    print("0: %s" % (get_cpumodel(info['0'])))
