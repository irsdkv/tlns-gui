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
    packages=['tlns_gui'],
    scripts=['scripts/tlns_gui.py'],
    package_data={'drone_planner': ['data']},
    install_requires=[
        'PyQt5==5.15.4'
    ],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
    ],
)
