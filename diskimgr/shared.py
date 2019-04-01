#! /usr/bin/env python3
"""Shared functions module"""

import os
import glob
import hashlib
import datetime
import pytz

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
