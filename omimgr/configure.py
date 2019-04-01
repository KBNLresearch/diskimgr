#! /usr/bin/env python3

"""Post-install / configuration script for omimgr"""

import os
import io
import json
import sys
import argparse


def parseCommandLine(parser):
    """Parse command line"""

    parser.add_argument('--remove', '-r',
                        action='store_true',
                        dest='removeFlag',
                        default=False,
                        help='remove all omimgr configuration files')
    # Parse arguments
    args = parser.parse_args()
    return args


def errorExit(msg):
    """Print error to stderr and exit"""
    msgString = ('ERROR: ' + msg + '\n')
    sys.stderr.write(msgString)
    sys.exit(1)

def infoMessage(msg):
    """Print message to stderr"""
    msgString = ('INFO: ' + msg + '\n')
    sys.stderr.write(msgString)

def writeConfigFile(configRootDir, removeFlag):
    """Create configuration file"""

    # Create configuration directory under configRootDir

    configDir = os.path.join(configRootDir, 'omimgr')

    if not removeFlag:
        if not os.path.isdir(configDir):
            os.mkdir(configDir)

    # Path to configuration file
    fConfig = os.path.join(configDir, 'omimgr.json')

    # Dictionary with items in configuration file
    configSettings = {}
    configSettings['retries'] = '4'
    configSettings['checksumFileName'] = 'checksums.sha512'
    configSettings['logFileName'] = 'omimgr.log'
    configSettings['metadataFileName'] = 'metadata.json'
    configSettings['omDevice'] = '/dev/sr0'
    configSettings['prefix'] = 'disc'
    configSettings['extension'] = 'iso'
    configSettings['rescueDirectDiscMode'] = 'False'
    configSettings['autoRetry'] = 'False'
    configSettings['readCommand'] = 'readom'
    configSettings['timeZone'] = 'Europe/Amsterdam'
    configSettings['defaultDir'] = ''

    if not removeFlag:
        # Write to configuration file in json format
        infoMessage('writing configuration file ' + fConfig)
        with io.open(fConfig, 'w', encoding='utf-8') as f:
            json.dump(configSettings, f, indent=4, sort_keys=True)
    else:
        if os.path.isfile(fConfig):
            infoMessage('removing configuration file ' + fConfig)
            os.remove(fConfig)
        if os.path.isdir(configDir):
            infoMessage('removing configuration directory ' + configDir)
            os.rmdir(configDir)

def writeDesktopFiles(packageDir, applicationsDir, desktopDir, removeFlag):
    """Creates desktop files in /usr/share/applications and on desktop"""

    # Needed to change file permissions
    sudoUID = os.environ.get('SUDO_UID')
    sudoGID = os.environ.get('SUDO_GID')

    # Full path to config and launcher scripts
    pathName = os.path.abspath(os.path.dirname(sys.argv[0]))

    # Locate icon file in package
    iconFile = os.path.join(packageDir, 'icons', 'omimgr.png')
    if not os.path.isfile(iconFile):
        msg = 'cannot find icon file'
        errorExit(msg)

    fApplications = os.path.join(applicationsDir, 'omimgr.desktop')

    # List of desktop file lines
    desktopList = []
    desktopList.append('[Desktop Entry]')
    desktopList.append('Type=Application')
    desktopList.append('Encoding=UTF-8')
    desktopList.append('Name=omimgr')
    desktopList.append('Comment=Simple optical media imaging and extraction tool')
    desktopList.append('Exec=' + os.path.join(pathName, 'omimgr'))
    desktopList.append('Icon=' + iconFile)
    desktopList.append('Terminal=false')
    desktopList.append('Categories=Utility;System;GTK')

    # Write desktop file to applications directory
    if not removeFlag:
        try:
            infoMessage('creating desktop file ' + fApplications)
            with io.open(fApplications, 'w', encoding='utf-8') as fA:
                for line in desktopList:
                    fA.write(line + '\n')
        except:
            msg = 'Failed to create ' + fApplications
            errorExit(msg)
    else:
        if os.path.isfile(fApplications):
            infoMessage('removing desktop file ' + fApplications)
            os.remove(fApplications)

def main():
    """
    Creates the following items:
    - configuration directory omimgr in ~/.config/ or /etc/
    - configuration file in configuration directory
    - desktop file in  ~/.local/share/applications/ or /usr/share/applications
    If the --remove / -r switch is given the above items
    are removed (if they exist)
    """

    # Parse command line
    parser = argparse.ArgumentParser(description='omimgr configuration tool')
    args = parseCommandLine(parser)
    removeFlag = args.removeFlag

    # Get evironment variables
    sudoUser = os.environ.get('SUDO_USER')

    # Package directory
    packageDir = os.path.dirname(os.path.abspath(__file__))

    # Current home directory
    try:
        # If executed as root, return normal user's home directory
        homeDir = os.path.normpath('/home/'+ sudoUser)
    except TypeError:
        #sudoUser doesn't exist if not executed as root
        homeDir = os.path.normpath(os.path.expanduser("~"))

    # Get locations of configRootDir and applicationsDir,
    # depending of install type (which is inferred from packageDir)

    if packageDir.startswith(homeDir):
        # Local install: store everything in user's home dir
        globalInstall = False
        configRootDir = os.path.join(homeDir, '.config/')
        applicationsDir = os.path.join(homeDir, '.local/share/applications/')
    else:
        # Global install
        globalInstall = True
        configRootDir = os.path.normpath('/etc/')
        applicationsDir = os.path.normpath('/usr/share/applications')

    # Desktop directory
    desktopDir = os.path.join(homeDir, 'Desktop/')

    # For a global installation this script must be run as root
    if globalInstall and sudoUser is None:
        msg = 'this script must be run as root for a global installation'
        errorExit(msg)

    # Check if directories exist and that they are writable
    if not os.access(configRootDir, os.W_OK | os.X_OK):
        msg = 'cannot write to ' + configRootDir
        errorExit(msg)

    if not os.access(applicationsDir, os.W_OK | os.X_OK):
        msg = 'cannot write to ' + applicationsDir
        errorExit(msg)

    if not os.access(desktopDir, os.W_OK | os.X_OK):
        msg = 'cannot write to ' + desktopDir
        errorExit(msg)

    writeConfigFile(configRootDir, removeFlag)
    writeDesktopFiles(packageDir, applicationsDir, desktopDir, removeFlag)
    infoMessage('omimgr configuration completed successfully!')


if __name__ == "__main__":
    main()
