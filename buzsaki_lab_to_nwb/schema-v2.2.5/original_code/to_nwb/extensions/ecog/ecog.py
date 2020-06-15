import os

from pynwb import load_namespaces
from ..auto_class import get_class, get_multi_container

import numpy as np

filepath = os.path.realpath(__file__)
basedir = os.path.split(filepath)[0]
name = 'ecog'

load_namespaces(os.path.join(basedir, name + '.namespace.yaml'))


def surface_init_add(faces, vertices, **kwargs):
    if np.max(faces) >= len(vertices):
        raise ValueError('index of faces exceeds number vertices for {}. '
                         'Faces should be 0-indexed, not 1-indexed'.
                         format(name))
    if np.min(faces < 0):
        raise ValueError('faces hold indices of vertices and should be non-negative')


Surface = get_class(name, 'Surface', surface_init_add)

CorticalSurfaces = get_multi_container(name, 'CorticalSurfaces', Surface)
