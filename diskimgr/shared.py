#! /usr/bin/env python3
"""Shared functions module"""

import os
import glob
import hashlib
import datetime
import pytz
import fcntl
import struct
from os.path import basename, dirname

def generate_file_sha512(fileIn):
    """Generate sha512 hash of file"""

    # fileIn is read in chunks to ensure it will work with (very) large files as well
    # Adapted from: http://stackoverflow.com/a/1131255/1209004

    blocksize = 2**20
    m = hashlib.sha512()
    with open(fileIn, "rb") as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()


def checksumDirectory(directory, extension, checksumFile):
    """Calculate checksums for all files in directory"""

    # All files in directory
    allFiles = glob.glob(directory + "/*." + extension)

    # Dictionary for storing results
    checksums = {}

    for thisFile in allFiles:
        hashString = generate_file_sha512(thisFile)
        fName = os.path.basename(thisFile)
        checksums[fName] = hashString

    # Write checksum file
    try:
        fChecksum = open(checksumFile, "w", encoding="utf-8")
        for fName in checksums:
            lineOut = checksums[fName] + " " + fName + '\n'
            fChecksum.write(lineOut)
        fChecksum.close()
        wroteChecksums = True
    except IOError:
        wroteChecksums = False

    return wroteChecksums, checksums

def generateDateTime(timeZone):
    """Generate date / time string in ISO format with added time zone info"""

    dateTime = datetime.datetime.now()
    pst = pytz.timezone(timeZone)
    dateTime = pst.localize(dateTime)
    dateTimeFormatted = dateTime.isoformat()
    return dateTimeFormatted

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

def getDeviceSize(devPath):
    """Return size of device in bytes"""
    req = 0x80081272 # BLKGETSIZE64, result is bytes as unsigned 64-bit integer (uint64)
    buf = ' ' * 8
    fmt = 'L'

    with open(devPath) as dev:
        buf = fcntl.ioctl(dev.fileno(), req, buf)
    noBytes = struct.unpack(fmt, buf)[0]
    return noBytes

def getBlockDevices():
    """
    Return information about block devices and underlying partitions
    Source: adapted from https://codereview.stackexchange.com/a/152527
    """

    deviceInfo = []

    # Devices
    drive_glob = '/sys/block/*/device'
    for d in glob.glob(drive_glob):
        deviceName = basename(dirname(d))
        devicePath = '/dev/' + deviceName
        try:
            noBytes = getDeviceSize(devicePath)
            deviceInfo.append([devicePath, sizeof_fmt(noBytes)])
        except OSError:
            pass

        # Partitions
        partition_glob = '/sys/block/{0}/*/start'.format(deviceName)
        for p in glob.glob(partition_glob):
            devicePath = '/dev/' + basename(dirname(p))
            try:
                noBytes = getDeviceSize(devicePath)
                deviceInfo.append([devicePath, sizeof_fmt(noBytes)])
            except OSError:
                pass
    return deviceInfo
