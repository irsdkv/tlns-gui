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
             'scripts/tlns_serial_testing.py'],
    package_data={'drone_planner': ['data']},
    install_requires=[
        'PyQt5==5.15.4',
        'QtAwesome==0.5.8',
        'asyncqt==0.7.0',
        'toml==0.10.2',
        'bitarray==2.1.0',
        'pyserial==3.5'
    ],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
    ],
)
