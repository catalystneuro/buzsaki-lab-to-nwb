# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

# Get the long description from the README file
with open('README.md', 'r') as f:
    long_description = f.read()

setup(name='buzsaki_lab_to_nwb',
      version='0.0.1',
      description='NWB conversion scripts, functions, and classes for the Buzsaki lab.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Cody Baker, Luiz Tauffer and Ben Dichter',
      email='ben.dichter@gmail.com',
      packages=find_packages(),
      include_package_data=True,
      install_requires=[
          'matplotlib', 'cycler', 'scipy', 'numpy', 'jupyter', 'xlrd', 'h5py', 'pynwb', 'spikeextractors', 'lxml',
          'typing', 'nwbn-conversion-tools'],
      )
