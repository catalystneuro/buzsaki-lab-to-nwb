import numpy as np
from datetime import datetime
import h5py

from pynwb.spec import (NWBGroupSpec, NWBDatasetSpec, NWBNamespaceBuilder)
from pynwb import get_class, load_namespaces, NWBHDF5IO, NWBFile


project_name = 'simulation_output'
ns_path = project_name + '.namespace.yaml'
ext_source = project_name + '.extensions.yaml'
ns_builder = NWBNamespaceBuilder(project_name, project_name)


def build_ext():
    datasets = [
        NWBDatasetSpec(doc='list of cell ids',
                       dtype='uint32',
                       shape=(None,),
                       name='gid',
                       quantity='?', dims=('cells',)),
        NWBDatasetSpec(doc='index pointer',
                       dtype='uint64',
                       shape=(None,),
                       name='index_pointer', dims=('cells',)),
        NWBDatasetSpec(doc='cell compartment ids corresponding to a given column in the data',
                       dtype='uint32',
                       shape=(None,),
                       name='element_id', dims=('compartments',)),
        NWBDatasetSpec(doc='relative position of recording within a given compartment',
                       dtype='float',
                       shape=(None, None),
                       name='element_pos', dims=('compartments', 'position'))
    ]

    cont_data = NWBGroupSpec(doc='A spec for storing cell recording variables',
                             datasets=datasets,
                             neurodata_type_inc='TimeSeries',
                             neurodata_type_def='CompartmentSeries')

    ns_builder.add_spec(ext_source, cont_data)
    ns_builder.export(ns_path)


def build_toy_example():
    load_namespaces(ns_path)
    CompartmentSeries = get_class('CompartmentSeries', project_name)
    membrane_potential = CompartmentSeries(source='source',
                                           name='membrane_potential',
                                           gid=[1, 2, 3],
                                           index_pointer=[1, 2, 3],
                                           cell_var='Membrane potential (mV)',
                                           data=[[1., 2., 4.], [1., 2., 4.]],
                                           timestamps=np.arange(2),
                                           element_id=[0, 0, 0],
                                           element_pos=[1., 1., 1.],
                                           unit='µV')

    nwbfile = NWBFile(source='source', session_description='session_description',
                      identifier='identifier', session_start_time=datetime.now(),
                      file_create_date=datetime.now(), institution='institution',
                      lab='lab')

    module = nwbfile.create_processing_module(name='membrane_potential',
                                              source='source',
                                              description='description')
    module.add_container(membrane_potential)

    with NWBHDF5IO('mem_potential_toy.nwb', mode='w') as io:
        io.write(nwbfile)


def build_real_example():
    load_namespaces(ns_path)
    VarTable = get_class('VarTable', project_name)
    input_data = h5py.File('sim_data/cell_vars.h5', 'r')
    vmtable = VarTable(source='source',
                       name='vm_table',
                       data=np.array(input_data['/v/data']),
                       gid=np.array(input_data['mapping/gids']),
                       index_pointer=np.array(input_data['mapping/index_pointer']),
                       cell_var='Membrane potential (mV)',
                       element_id=np.array(input_data['mapping/element_id']),
                       element_pos=np.array(input_data['mapping/element_pos']))

    nwbfile = NWBFile(source='source', session_description='session_description',
                      identifier='identifier', session_start_time=datetime.now(),
                      file_create_date=datetime.now(), institution='institution',
                      lab='lab')

    module = nwbfile.create_processing_module(name='name', source='source',
                                              description='description')
    module.add_container(vmtable)

    io = NWBHDF5IO('mem_potential_toy.nwb', mode='w')
    io.write(nwbfile)
    io.close()


if __name__ == '__main__':
    build_ext()
    build_toy_example()
    #build_real_example()
