#!/usr/bin/env python
import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "tlns_gui",
    version = "0.0.1",
    author = "Ildar Sadykov",
    author_email = "irsdkv@gmail.com",
    description = ("tlns_gui"),
    license = "MIT",
    keywords = "tlns",
    scripts=['scripts/tlns_gui.py',
             'scripts/tlns_serial_testing.py',
             'scripts/bcb_prototype.py'],
    package_data={'tlns_test': ['data']},
    install_requires=[
        'QtAwesome==0.5.8',
        'asyncqt==0.7.0',
        'toml==0.10.2',
        'bitarray==2.1.0',
        'pyserial==3.5',
        'dearpygui==0.8.64'
    ],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
    ],
)
