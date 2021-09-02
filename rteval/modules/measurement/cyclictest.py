#
#   cyclictest.py - object to manage a cyclictest executable instance
#
#   Copyright 2009 - 2013   Clark Williams <williams@redhat.com>
#   Copyright 2012 - 2013   David Sommerseth <davids@redhat.com>
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
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#   For the avoidance of doubt the "preferred form" of this code is one which
#   is in an open unpatent encumbered format. Where cryptographic key signing
#   forms part of the process of creating an executable the information
#   including keys needed to generate an equivalently functional executable
#   are deemed to be part of the source code.
#

import os
import subprocess
import signal
import time
import tempfile
import math
import libxml2
from rteval.Log import Log
from rteval.modules import rtevalModulePrototype
from rteval.misc import expand_cpulist, online_cpus, cpuinfo

class RunData:
    '''class to keep instance data from a cyclictest run'''
    def __init__(self, coreid, datatype, priority, logfnc):
        self.__id = coreid
        self.__type = datatype
        self.__priority = int(priority)
        self.__description = ''
        # histogram of data
        self.__samples = {}
        self.__numsamples = 0
        self.__min = 100000000
        self.__max = 0
        self.__stddev = 0.0
        self.__mean = 0.0
        self.__mode = 0.0
        self.__median = 0.0
        self.__range = 0.0
        self.__mad = 0.0
        self._log = logfnc

    def __str__(self):
        retval = "id:         %s\n" % self.__id
        retval += "type:       %s\n" % self.__type
        retval += "numsamples: %d\n" % self.__numsamples
        retval += "min:        %d\n" % self.__min
        retval += "max:        %d\n" % self.__max
        retval += "stddev:     %f\n" % self.__stddev
        retval += "mad:        %f\n" % self.__mad
        retval += "mean:       %f\n" % self.__mean
        return retval

    def sample(self, value):
        self.__samples[value] += self.__samples.setdefault(value, 0) + 1
        if value > self.__max:
            self.__max = value
        if value < self.__min:
            self.__min = value
        self.__numsamples += 1

    def bucket(self, index, value):
        self.__samples[index] = self.__samples.setdefault(index, 0) + value
        if value and index > self.__max:
            self.__max = index
        if value and index < self.__min:
            self.__min = index
        self.__numsamples += value

    def reduce(self):

        # check to see if we have any samples and if we
        # only have 1 (or none) set the calculated values
        # to zero and return
        if self.__numsamples <= 1:
            self._log(Log.DEBUG, "skipping %s (%d samples)" % (self.__id, self.__numsamples))
            self.__mad = 0
            self.__stddev = 0
            return

        self._log(Log.INFO, "reducing %s" % self.__id)
        total = 0
        keys = list(self.__samples.keys())
        keys.sort()

        mid = self.__numsamples / 2

        # mean, mode, and median
        occurances = 0
        lastkey = -1
        for i in keys:
            if mid > total and mid <= (total + self.__samples[i]):
                if self.__numsamples & 1 and mid == total+1:
                    self.__median = (lastkey + i) / 2
                else:
                    self.__median = i
            total += (i * self.__samples[i])
            if self.__samples[i] > occurances:
                occurances = self.__samples[i]
                self.__mode = i
        self.__mean = float(total) / float(self.__numsamples)

        # range
        for i in keys:
            if self.__samples[i]:
                low = i
                break
        high = keys[-1]
        while high and self.__samples[high] == 0:
            high -= 1
        self.__range = high - low

        # Mean Absolute Deviation and standard deviation
        madsum = 0
        varsum = 0
        for i in keys:
            madsum += float(abs(float(i) - self.__mean) * self.__samples[i])
            varsum += float(((float(i) - self.__mean) ** 2) * self.__samples[i])
        self.__mad = madsum / self.__numsamples
        self.__stddev = math.sqrt(varsum / (self.__numsamples - 1))


    def MakeReport(self):
        rep_n = libxml2.newNode(self.__type)
        if self.__type == 'system':
            rep_n.newProp('description', self.__description)
        else:
            rep_n.newProp('id', str(self.__id))
            rep_n.newProp('priority', str(self.__priority))

        stat_n = rep_n.newChild(None, 'statistics', None)

        stat_n.newTextChild(None, 'samples', str(self.__numsamples))

        if self.__numsamples > 0:
            n = stat_n.newTextChild(None, 'minimum', str(self.__min))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'maximum', str(self.__max))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'median', str(self.__median))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'mode', str(self.__mode))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'range', str(self.__range))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'mean', str(self.__mean))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'mean_absolute_deviation', str(self.__mad))
            n.newProp('unit', 'us')

            n = stat_n.newTextChild(None, 'standard_deviation', str(self.__stddev))
            n.newProp('unit', 'us')

            hist_n = rep_n.newChild(None, 'histogram', None)
            hist_n.newProp('nbuckets', str(len(self.__samples)))
            keys = list(self.__samples.keys())
            keys.sort()
            for k in keys:
                if self.__samples[k] == 0:
                    # Don't report buckets without any samples
                    continue
                b_n = hist_n.newChild(None, 'bucket', None)
                b_n.newProp('index', str(k))
                b_n.newProp('value', str(self.__samples[k]))

        return rep_n


class Cyclictest(rtevalModulePrototype):
    def __init__(self, config, logger=None):
        rtevalModulePrototype.__init__(self, 'measurement', 'cyclictest', logger)
        self.__cfg = config

        # Create a RunData object per CPU core
        self.__numanodes = int(self.__cfg.setdefault('numanodes', 0))
        self.__priority = int(self.__cfg.setdefault('priority', 95))
        self.__buckets = int(self.__cfg.setdefault('buckets', 2000))
        self.__reportdir = self.__cfg.setdefault('reportdir', os.getcwd())
        self.__numcores = 0
        self.__cpus = []
        self.__cyclicdata = {}
        self.__sparse = False

        if self.__cfg.cpulist:
            self.__cpulist = self.__cfg.cpulist
            self.__cpus = expand_cpulist(self.__cpulist)
            self.__sparse = True
        else:
            self.__cpus = online_cpus()

        # Get the cpuset from the environment
        cpuset = os.sched_getaffinity(0)

        # Convert the elements to strings
        cpuset = [str(c) for c in cpuset]

        # Only include cpus that are in the cpuset
        self.__cpus = [c for c in self.__cpus if c in cpuset]

        self.__numcores = len(self.__cpus)

        info = cpuinfo()

        # create a RunData object for each core we'll measure
        for core in self.__cpus:
            self.__cyclicdata[core] = RunData(core, 'core', self.__priority,
                                              logfnc=self._log)
            self.__cyclicdata[core].description = info[core]['model name']

        # Create a RunData object for the overall system
        self.__cyclicdata['system'] = RunData('system',
                                              'system', self.__priority,
                                              logfnc=self._log)
        self.__cyclicdata['system'].description = ("(%d cores) " % self.__numcores) + info['0']['model name']

        if self.__sparse:
            self._log(Log.DEBUG, "system using %d cpu cores" % self.__numcores)
        else:
            self._log(Log.DEBUG, "system has %d cpu cores" % self.__numcores)
        self.__started = False
        self.__cyclicoutput = None
        self.__breaktraceval = None


    @staticmethod
    def __get_debugfs_mount():
        ret = None
        mounts = open('/proc/mounts')
        for l in mounts:
            field = l.split()
            if field[2] == "debugfs":
                ret = field[1]
                break
        mounts.close()
        return ret

    def _open_logfile(self, name):
        return open(os.path.join(self.__reportdir, "logs", name), 'w+b')

    def _WorkloadSetup(self):
        self.__cyclicprocess = None


    def _WorkloadBuild(self):
        self._setReady()


    def _WorkloadPrepare(self):
        self.__interval = 'interval' in self.__cfg and '-i%d' % int(self.__cfg.interval) or ""

        self.__cmd = ['cyclictest',
                      self.__interval,
                      '-qmu',
                      '-h %d' % self.__buckets,
                      "-p%d" % int(self.__priority),
                      ]
        if self.__sparse:
            self.__cmd.append('-t%d' % self.__numcores)
            self.__cmd.append('-a%s' % self.__cpulist)
        else:
            self.__cmd.append('-t')
            self.__cmd.append('-a')

        if 'threads' in self.__cfg and self.__cfg.threads:
            self.__cmd.append("-t%d" % int(self.__cfg.threads))

        if 'breaktrace' in self.__cfg and self.__cfg.breaktrace:
            self.__cmd.append("-b%d" % int(self.__cfg.breaktrace))
            self.__cmd.append("--tracemark")

        # Buffer for cyclictest data written to stdout
        self.__cyclicoutput = self._open_logfile('cyclictest.stdout')


    def _WorkloadTask(self):
        if self.__started:
            # Don't restart cyclictest if it is already runing
            return

        self._log(Log.DEBUG, "starting with cmd: %s" % " ".join(self.__cmd))
        self.__nullfp = os.open('/dev/null', os.O_RDWR)

        debugdir = self.__get_debugfs_mount()
        if 'breaktrace' in self.__cfg and self.__cfg.breaktrace and debugdir:
            # Ensure that the trace log is clean
            trace = os.path.join(debugdir, 'tracing', 'trace')
            fp = open(os.path.join(trace), "w")
            fp.write("0")
            fp.flush()
            fp.close()

        self.__cyclicoutput.seek(0)
        try:
            self.__cyclicprocess = subprocess.Popen(self.__cmd,
                                                    stdout=self.__cyclicoutput,
                                                    stderr=self.__nullfp,
                                                    stdin=self.__nullfp)
            self.__started = True
        except OSError:
            self.__started = False


    def WorkloadAlive(self):
        if self.__started:
            return self.__cyclicprocess.poll() is None
        return False


    def _WorkloadCleanup(self):
        if not self.__started:
            return
        while self.__cyclicprocess.poll() is None:
            self._log(Log.DEBUG, "Sending SIGINT")
            os.kill(self.__cyclicprocess.pid, signal.SIGINT)
            time.sleep(2)

        # now parse the histogram output
        self.__cyclicoutput.seek(0)
        for line in self.__cyclicoutput:
            line = bytes.decode(line)
            if line.startswith('#'):
                # Catch if cyclictest stopped due to a breaktrace
                if line.startswith('# Break value: '):
                    self.__breaktraceval = int(line.split(':')[1])
                continue

            # Skipping blank lines
            if not line:
                continue

            vals = line.split()
            if not vals:
                # If we don't have any values, don't try parsing
                continue

            try:
                index = int(vals[0])
            except:
                self._log(Log.DEBUG, "cyclictest: unexpected output: %s" % line)
                continue

            for i, core in enumerate(self.__cpus):
                self.__cyclicdata[core].bucket(index, int(vals[i+1]))
                self.__cyclicdata['system'].bucket(index, int(vals[i+1]))

        # generate statistics for each RunData object
        for n in list(self.__cyclicdata.keys()):
            #print "reducing self.__cyclicdata[%s]" % n
            self.__cyclicdata[n].reduce()
            #print self.__cyclicdata[n]

        self._setFinished()
        self.__started = False
        os.close(self.__nullfp)
        del self.__nullfp


    def MakeReport(self):
        rep_n = libxml2.newNode('cyclictest')
        rep_n.newProp('command_line', ' '.join(self.__cmd))

        # If it was detected cyclictest was aborted somehow,
        # report the reason
        abrt_n = libxml2.newNode('abort_report')
        abrt = False
        if self.__breaktraceval:
            abrt_n.newProp('reason', 'breaktrace')
            btv_n = abrt_n.newChild(None, 'breaktrace', None)
            btv_n.newProp('latency_threshold', str(self.__cfg.breaktrace))
            btv_n.newProp('measured_latency', str(self.__breaktraceval))
            abrt = True

        # Only add the <abort_report/> node if an abortion happened
        if abrt:
            rep_n.addChild(abrt_n)

        rep_n.addChild(self.__cyclicdata["system"].MakeReport())
        for thr in self.__cpus:
            if str(thr) not in self.__cyclicdata:
                continue
            rep_n.addChild(self.__cyclicdata[str(thr)].MakeReport())

        return rep_n



def ModuleInfo():
    return {"parallel": True,
            "loads": True}



def ModuleParameters():
    return {"interval": {"descr": "Base interval of the threads in microseconds",
                         "default": 100,
                         "metavar": "INTV_US"},
            "buckets":  {"descr": "Histogram width",
                         "default": 2000,
                         "metavar": "NUM"},
            "priority": {"descr": "Run cyclictest with the given priority",
                         "default": 95,
                         "metavar": "PRIO"},
            "breaktrace": {"descr": "Send a break trace command when latency > USEC",
                           "default": None,
                           "metavar": "USEC"}
            }



def create(params, logger):
    return Cyclictest(params, logger)


if __name__ == '__main__':
    from rteval.rtevalConfig import rtevalConfig

    l = Log()
    l.SetLogVerbosity(Log.INFO|Log.DEBUG|Log.ERR|Log.WARN)

    cfg = rtevalConfig({}, logger=l)
    prms = {}
    modprms = ModuleParameters()
    for c, p in list(modprms.items()):
        prms[c] = p['default']
    cfg.AppendConfig('cyclictest', prms)

    cfg_ct = cfg.GetSection('cyclictest')
    cfg_ct.reportdir = "."
    cfg_ct.buckets = 200
    # cfg_ct.breaktrace = 30

    runtime = 10

    c = Cyclictest(cfg_ct, l)
    c._WorkloadSetup()
    c._WorkloadPrepare()
    c._WorkloadTask()
    time.sleep(runtime)
    c._WorkloadCleanup()
    rep_n = c.MakeReport()

    xml = libxml2.newDoc('1.0')
    xml.setRootElement(rep_n)
    xml.saveFormatFileEnc('-', 'UTF-8', 1)
