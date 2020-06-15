import os

from pynwb import load_namespaces
from ..auto_class import get_class

filepath = os.path.realpath(__file__)
basedir = os.path.split(filepath)[0]

load_namespaces(os.path.join(basedir, 'time_frequency.namespace.yaml'))


HilbertSeries = get_class('time_frequency', 'HilbertSeries')
