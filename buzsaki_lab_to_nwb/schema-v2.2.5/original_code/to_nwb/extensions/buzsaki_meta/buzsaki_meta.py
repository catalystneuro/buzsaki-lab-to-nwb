from pynwb import load_namespaces

from ..auto_class import get_class, get_multi_container

# load custom classes
namespace = 'buzsaki_meta'
ns_path = namespace + '.namespace.yaml'
ext_source = namespace + '.extensions.yaml'
load_namespaces(ns_path)

BuzSubject = get_class(namespace, 'BuzSubject')
Histology = get_class(namespace, 'Histology')
Probe = get_class(namespace, 'Probe')

VirusInjection = get_class(namespace, 'VirusInjection')
VirusInjections = get_multi_container(namespace, 'VirusInjections', VirusInjection)

Surgery = get_class(namespace, 'Surgery')
Surgeries = get_multi_container(namespace, 'Surgeries', Surgery)

Manipulation = get_class(namespace, 'Manipulation')
Manipulations = get_multi_container(namespace, 'Manipulations', Manipulation)