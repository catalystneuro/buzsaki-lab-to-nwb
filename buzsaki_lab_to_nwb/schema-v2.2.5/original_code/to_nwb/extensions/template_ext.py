"""
A cookie-cutter guide for creating your own extension.
"""
from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, NWBAttributeSpec, RefSpec


namespace = 'template [CHANGE TO NAME]'
ns_path = namespace + ".namespace.yaml"
ext_source = namespace + ".extensions.yaml"

spec = NWBGroupSpec(
    neurodata_type_def='',
    neurodata_type_inc='NWBDataInterface',
    quantity='?',
    doc='',
    groups=[],
    attributes=[
        NWBAttributeSpec(name='',
                         doc='',
                         dtype='',
                         required=False),
        NWBAttributeSpec(name='help',
                         doc='help',
                         dtype='text',
                         value='ENTER HELP INFO HERE')
        ],
    datasets=[
        NWBDatasetSpec(name='',
                       doc='',
                       dtype='',
                       shape=())
    ]
)

ns_builder = NWBNamespaceBuilder(doc=namespace + ' extensions', name=namespace,
                                 version='1.0', author='Ben Dichter',
                                 contact='bendichter@gmail.com')
specs = (spec,)
for spec in specs:
    ns_builder.add_spec(ext_source, spec)
ns_builder.export(ns_path)

