from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, AttributeSpec
from pynwb import get_class, load_namespaces


## spec for
name = 'simulation_output'
ns_path = name + '.namespace.yaml'
ext_source = name + '.extensions.yaml'

gid_spec = NWBDatasetSpec(doc='global id for neuron',
                          shape=(None, 1),
                          name='cell_index', dtype='int', quantity='?')

values = AttributeSpec(shape=(None, 1), name='labels', dtype='str',
                       required=True, doc='these are the values')

cat_data_spec = NWBDatasetSpec(name='data', shape=(None, 1), dtype='int',
                               doc='indices into values for each gid in order',
                               attributes=[values])

cat_cell_info = NWBGroupSpec(neurodata_type_def='CatCellInfo',
                             doc='Categorical Cell Info',
                             datasets=[gid_spec, cat_data_spec],
                             neurodata_type_inc='NWBDataInterface')

# export
ns_builder = NWBNamespaceBuilder(name + ' extensions', name)
for spec in [cat_cell_info]:
    ns_builder.add_spec(ext_source, spec)
ns_builder.export(ns_path)




'''

EXAMPLE USAGE:


from pynwb import get_class, load_namespaces, NWBHDF5IO

ns_path = name + '.namespace.yaml'
load_namespaces(ns_path)

CatCellInfo = get_class('CatCellInfo', name)

import numpy as np
from pynwb import NWBFile
from datetime import datetime

cell_types = ['A','A','B','B','C','A']

[types_labels, types_indices] = np.unique(cell_types, return_inverse=True)
cci_obj = CatCellInfo(source='source', name='cell_type', labels=list(types_labels), 
                      data=types_indices, cell_index=np.arange(len(cell_types)))

nwbfile = NWBFile(
    source='source', session_description='session_description',
    identifier='identifier', session_start_time=datetime.now(),
    file_create_date=datetime.now(), institution='institution',
    lab='lab')

module = nwbfile.create_processing_module(
    name='name', source='source', description='description')
module.add_container(cci_obj)

with NWBHDF5IO('cat_cell_test.nwb', 'w') as io:
    io.write(nwbfile)

'''