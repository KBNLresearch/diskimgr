#! /usr/bin/env python3
"""This module contains the Disk class with functions that
do the actual imaging.
"""

import os
import fcntl
import io
import json
import time
import logging
import glob
import pathlib
from shutil import which
from isolyzer import isolyzer
from . import wrappers
from . import config
from . import shared

class Disk:
    """Disk class"""
    def __init__(self):
        """initialise Disk class instance"""

        # Input collected by GUI / CLI
        self.dirOut = ''
        self.blockDevice = ''
        self.blockSize = ''
        self.blockSizeDefault = ''
        self.readMethod = ''
        self.retries = ''
        self.ddVersion = ''
        self.ddRescueVersion = ''
        self.prefix = ''
        self.extension = ''
        self.rescueDirectDiscMode = ''
        self.autoRetry = ''
        self.retriesDefault = ''
        self.identifier = ''
        self.description = ''
        self.notes = ''
        # Input validation flags
        self.dirOutIsDirectory = False
        self.outputExistsFlag = False
        self.deviceExistsFlag = False
        self.discInTrayFlag = False
        self.dirOutIsWritable = False
        # Flags that define if dependencies are installed
        self.ddrescueInstalled = False
        self.ddInstalled = False
        # Config file location, depends on package directory
        packageDir = os.path.dirname(os.path.abspath(__file__))
        homeDir = os.path.normpath(os.path.expanduser("~"))
        if packageDir.startswith(homeDir):
            self.configFile = os.path.join(homeDir, '.config/diskimgr/diskimgr.json')
        else:
            self.configFile = os.path.normpath('/etc/diskimgr/diskimgr.json')

        # Miscellaneous attributes
        self.logFile = ''
        self.imageFile = ''
        self.mapFile = ''
        self.logFileName = ''
        self.checksumFileName = ''
        self.metadataFileName = ''
        self.finishedFlag = False
        self.omDeviceIOError = False
        self.successFlag = True
        self.interruptedFlag = False
        self.readErrorFlag = False
        self.configSuccess = True
        self.isolyzerSuccess = False
        self.imageTruncated = True
        self.timeZone = ''
        self.defaultDir = ''

    def getConfiguration(self):
        """read configuration file and set variables accordingly"""
        if not os.path.isfile(self.configFile):
            self.configSuccess = False

        # Read config file to dictionary
        try:
            with io.open(self.configFile, 'r', encoding='utf-8') as f:
                configDict = json.load(f)
        except:
            self.configSuccess = False

        ## TEST
        print(self.configSuccess)
        ## TEST

        if self.configSuccess:
            # Update class variables
            try:
                self.logFileName = configDict['logFileName']
                self.checksumFileName = configDict['checksumFileName']
                self.metadataFileName = configDict['metadataFileName']
                self.blockDevice = configDict['blockDevice']
                self.blockSize = configDict['blockSize']
                self.blockSizeDefault = self.blockSize
                self.prefix = configDict['prefix']
                self.extension = configDict['extension']
                self.rescueDirectDiscMode = configDict['rescueDirectDiscMode']
                self.autoRetry = configDict['autoRetry']
                # Convert rescueDirectDiscMode and autoRetry to Boolean
                self.rescueDirectDiscMode = bool(self.rescueDirectDiscMode == "True")
                self.autoRetry = bool(self.autoRetry == "True")
                self.retriesDefault = configDict['retries']
                self.timeZone = configDict['timeZone']
                self.defaultDir = configDict['defaultDir']
            except KeyError:
                self.configSuccess = False

    def getTrayStatus(self, drivePath):
        """Return status of CD tray, adapted from https://superuser.com/a/1367091/681049
        Statuses:
        1 = no disk in tray
        2 = tray open
        3 = reading tray
        4 = disk in tray
        """
        fd = os.open(drivePath, os.O_RDONLY | os.O_NONBLOCK)
        status = fcntl.ioctl(fd, 0x5326)
        os.close(fd)

        return status

    def validateInput(self):
        """Validate and pre-process input"""

        # Check if dirOut is a directory
        self.dirOutIsDirectory = os.path.isdir(self.dirOut)

        # Check if glob pattern for dirOut, prefix and extension matches existing files
        if glob.glob(self.dirOut + '/' + self.prefix + '*.' + self.extension):
            self.outputExistsFlag = True

        # Check if dirOut is writable
        self.dirOutIsWritable = os.access(self.dirOut, os.W_OK | os.X_OK)

        # Check if dd and ddrescue are installed

        if which("dd") is not None:
            self.ddInstalled = True
        if which("ddrescue") is not None:
            self.ddrescueInstalled = True

        # Get dd and ddrescue version strings
        self.ddVersion = wrappers.getVersion(['dd'])
        self.ddRescueVersion = wrappers.getVersion(['ddrescue'])

        # Check if selected block device exists
        p = pathlib.Path(self.blockDevice)
        self.deviceExistsFlag = p.is_block_device()

        # Check if disc is in tray
        if self.getTrayStatus(self.blockDevice) == 4:
            self.discInTrayFlag = True

        # Image file
        self.imageFile = os.path.join(self.dirOut, self.prefix + '.' + self.extension)

        # Ddrescue map file
        self.mapFile = os.path.join(self.dirOut, self.prefix + '.map')

        # Log file
        self.logFile = os.path.join(self.dirOut, self.logFileName)

    def processDisk(self):
        """Process a disk"""

        # Create dictionary for storing metadata (which are later written to file)
        metadata = {}

        # Write some general info to log file
        logging.info('***************************')
        logging.info('*** DISKIMGR EXTRACTION LOG ***')
        logging.info('***************************\n')
        logging.info('*** USER INPUT ***')
        logging.info('diskimgrVersion: ' + config.version)
        logging.info('dirOut: ' + self.dirOut)
        logging.info('blockDevice: ' + self.blockDevice)
        logging.info('readMethod: ' + self.readMethod)
        logging.info('maxRetries: ' + str(self.retries))
        logging.info('prefix: ' + self.prefix)
        logging.info('extension: ' + self.extension)
        logging.info('direct disc mode (ddrescue only): ' + str(self.rescueDirectDiscMode))
        logging.info('automatically retry with ddrecue on dd failure: ' + str(self.autoRetry))

        ## Acquisition start date/time
        acquisitionStart = shared.generateDateTime(self.timeZone)

        # Unmount disc
        args = ['umount', self.blockDevice]
        wrappers.umount(args)

        if self.readMethod == "dd":
            args = ['dd']
            args.append('retries=' + str(self.retries))
            args.append('dev=' + self.blockDevice)
            args.append('f=' + self.imageFile)
            readCmdLine, readExitStatus, self.readErrorFlag, self.interruptedFlag = wrappers.dd(args)
        elif self.readMethod == "ddrescue":
            args = ['ddrescue']
            if self.rescueDirectDiscMode:
                args.append('-d')
            args.append('-b')
            args.append('2048')
            args.append('-r' + str(self.retries))
            args.append('-v')
            args.append(self.blockDevice)
            args.append(self.imageFile)
            args.append(self.mapFile)
            readCmdLine, readExitStatus, self.readErrorFlag, self.interruptedFlag = wrappers.ddrescue(args)

        # Run isolyzer to verify if ISO is complete and extract volume identifier text string
        try:
            isolyzerResult = isolyzer.processImage(self.imageFile, 0)
            # Isolyzer status
            try:
                if isolyzerResult.find('statusInfo/success').text == "True":
                    self.isolyzerSuccess = True
                else:
                    self.isolyzerSuccess = False
            except AttributeError:
                self.isolyzerSuccess = False

            # Is ISO image smaller than expected (if True, this indicates the image may be truncated)
            try:
                self.imageTruncated = isolyzerResult.find('tests/smallerThanExpected').text
            except AttributeError:
                self.imageTruncated = True

        except IOError:
            self.isolyzerSuccess = False
            self.imageTruncated = True
        
        logging.info('isolyzerSuccess: ' + str(self.isolyzerSuccess))
        logging.info('imageTruncated: ' + str(self.imageTruncated))
        
        if self.readErrorFlag or self.interruptedFlag or self.imageTruncated or not self.isolyzerSuccess:
            self.successFlag = False

        # Create checksum file
        logging.info('*** Creating checksum file ***')
        checksumFile = os.path.join(self.dirOut, self.checksumFileName)
        writeFlag, checksums = shared.checksumDirectory(self.dirOut, self.extension, checksumFile)

        # Acquisition end date/time
        acquisitionEnd = shared.generateDateTime(self.timeZone)

        # Fill metadata dictionary
        metadata['identifier'] = self.identifier
        metadata['description'] = self.description
        metadata['notes'] = self.notes
        metadata['diskimgrVersion'] = config.version
        metadata['blockDevice'] = self.blockDevice
        metadata['readMethod'] = self.readMethod
        if self.readMethod == "dd":
            metadata['readMethodVersion'] = self.ddVersion
        if self.readMethod == "ddrescue":
            metadata['readMethodVersion'] = self.ddRescueVersion
        metadata['readCommandLine'] = readCmdLine
        metadata['maxRetries'] = self.retries
        metadata['rescueDirectDiscMode'] = self.rescueDirectDiscMode
        metadata['autoRetry'] = self.autoRetry
        metadata['prefix'] = self.prefix
        metadata['extension'] = self.extension
        metadata['acquisitionStart'] = acquisitionStart
        metadata['acquisitionEnd'] = acquisitionEnd
        metadata['successFlag'] = self.successFlag
        metadata['isolyzerSuccess'] = self.isolyzerSuccess
        metadata['imageTruncated'] = self.imageTruncated
        metadata['interruptedFlag'] = self.interruptedFlag
        metadata['checksums'] = checksums
        metadata['checksumType'] = 'SHA-512'

        # Write metadata to file in json format
        logging.info('*** Writing metadata file ***')
        metadataFile = os.path.join(self.dirOut, self.metadataFileName)
        try:
            with io.open(metadataFile, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4, sort_keys=True)
        except IOError:
            self.successFlag = False
            logging.error('error while writing metadata file')

        logging.info('Success: ' + str(self.successFlag))

        if self.successFlag:
            wrappers.ejectDrive(self.blockDevice)
            logging.info('Disk processed without errors')
            logging.info('Ejecting disc')
        else:
            logging.error('One or more errors occurred while processing disc, '
                          'check log file for details')

        # Set finishedFlag
        self.finishedFlag = True

        # Wait 2 seconds to avoid race condition
        time.sleep(2)
