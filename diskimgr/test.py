import fcntl
import struct
import glob
from os.path import basename, dirname

def sizeof_fmt(num, suffix='B'):
    """
    Returns human-readable version of file size
    Source: https://stackoverflow.com/a/1094933
    """
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def getBlockDevices():
    """
    Return information about block devices and underlying partitions
    Source: adapted from https://codereview.stackexchange.com/a/152527
    """
    req = 0x80081272 # BLKGETSIZE64, result is bytes as unsigned 64-bit integer (uint64)
    buf = ' ' * 8
    fmt = 'L'
    deviceInfo = []

    # Devices
    drive_glob = '/sys/block/*/device'
    for d in glob.glob(drive_glob):
        deviceName = basename(dirname(d))
        devicePath = '/dev/' + deviceName
        try:
            with open(devicePath) as dev:
                buf = fcntl.ioctl(dev.fileno(), req, buf)
            noBytes = struct.unpack(fmt, buf)[0]
            deviceInfo.append([devicePath, sizeof_fmt(noBytes)])
        except OSError:
            pass

        # Partitions
        partition_glob = '/sys/block/{0}/*/start'.format(deviceName)
        for p in glob.glob(partition_glob):
            devicePath = '/dev/' + basename(dirname(p))
            try:
                with open(devicePath) as dev:
                    buf = fcntl.ioctl(dev.fileno(), req, buf)
                noBytes = struct.unpack(fmt, buf)[0]
                deviceInfo.append([devicePath, sizeof_fmt(noBytes)])
            except OSError:
                pass
    return deviceInfo


myDevices = getBlockDevices()
print(myDevices)
