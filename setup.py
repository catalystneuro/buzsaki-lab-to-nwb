from setuptools import setup
from codecs import open
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.md")) as f:
    long_description = f.read()

with open(os.path.join(here, "requirements.txt")) as f:
    install_requires = f.read().strip().split("\n")


setup(
    name="buzsaki-lab-to-nwb",
    version="0.4.0",
    description="NWB conversion scripts, functions, and classes for the Buzsaki lab.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ben Dichter, Cody Baker, and Luiz Tauffer",
    author_email="ben.dichter@gmail.com",
    url="https://github.com/catalystneuro/buzsaki-lab-to-nwb",
    python_requires=">=3.7",
    install_requires=install_requires,
)
