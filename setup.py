#!/usr/bin/env python
"""Setup script for diskimgr"""

import codecs
import os
import re
from setuptools import setup, find_packages


def read(*parts):
    """Read file and return contents"""
    path = os.path.join(os.path.dirname(__file__), *parts)
    with codecs.open(path, encoding='utf-8') as fobj:
        return fobj.read()


def find_version(*file_paths):
    """Return version number from main module"""
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


INSTALL_REQUIRES = [
    'setuptools',
    'pytz',
    'tkfilebrowser'
]

PYTHON_REQUIRES = '>=3.2'

setup(name='diskimgr',
      packages=find_packages(),
      version=find_version('diskimgr', 'diskimgr.py'),
      license='Apache License 2.0',
      install_requires=INSTALL_REQUIRES,
      python_requires=PYTHON_REQUIRES,
      platforms=['linux'],
      description='Optical media imager',
      long_description='Optical media imager/reader; wraps around readom and ddrescue tools',
      author='Johan van der Knijff',
      author_email='johan.vanderknijff@kb.nl',
      maintainer='Johan van der Knijff',
      maintainer_email='johan.vanderknijff@kb.nl',
      url='https://github.com/KBNLresearch/diskimgr',
      download_url=('https://github.com/KBNLresearch/diskimgr/archive/' +
                    find_version('diskimgr', 'diskimgr.py') + '.tar.gz'),
      package_data={'diskimgr': ['*.*', 'icons/*', 'pkexec/*']},
      zip_safe=False,
      entry_points={'gui_scripts': [
          'diskimgr = diskimgr.diskimgr:main'],
                    'console_scripts': [
                        'diskimgr = diskimgr.diskimgr:main',
                        'diskimgr-config = diskimgr.configure:main']},
      classifiers=[
          'Programming Language :: Python :: 3',]
     )
