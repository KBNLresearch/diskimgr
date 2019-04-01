#! /usr/bin/env python3
"""
omimgr, automated reading of optical media

Author: Johan van der Knijff
Research department,  KB / National Library of the Netherlands
"""

from .gui import main as guiLaunch
from . import config

__version__ = '0.2.1'

def main():
    """Launch GUI"""
    config.version = __version__
    guiLaunch()

main()
