#!/usr/bin/env python
import os
from setuptools import setup

# fake pbr version
os.environ['PBR_VERSION'] = "0.0.0"

setup(
    setup_requires=['pbr'],
    pbr=True,
)
