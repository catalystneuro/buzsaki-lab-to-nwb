import os

from pynwb import load_namespaces
from ..auto_class import get_class

filepath = os.path.realpath(__file__)
basedir = os.path.split(filepath)[0]
name = 'general'

load_namespaces(os.path.join(basedir, name + '.namespace.yaml'))


CatCellInfo = get_class(name, 'CatCellInfo')
#CatTimeSeries = get_class(name, 'CatTimeSeries')
