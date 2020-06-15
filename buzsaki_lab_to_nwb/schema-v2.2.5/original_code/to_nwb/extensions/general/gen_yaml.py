from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, \
    NWBAttributeSpec

namespace = 'general'
ns_path = namespace + '.namespace.yaml'
ext_source = namespace + '.extensions.yaml'

values = NWBAttributeSpec(name='values',
                          dtype='text',
                          doc='values that the indices are indexing',
                          shape=(None,))

cat_cell_info = NWBGroupSpec(
    neurodata_type_def='CatCellInfo',
    doc='Categorical Cell Info',
    attributes=[NWBAttributeSpec(
        name='help',
        doc='help',
        dtype='text',
        value='Categorical information about cells. For most cases the units tables is more appropriate. This '
              'structure can be used if you need multiple entries per cell')],
    datasets=[
        NWBDatasetSpec(doc='global id for neuron',
                       shape=(None,),
                       name='cell_index', dtype='int', quantity='?'),
        NWBDatasetSpec(name='indices',
                       doc='list of indices for values',
                       shape=(None,), dtype='int',
                       attributes=[values])],
    neurodata_type_inc='NWBDataInterface')

cat_timeseries = NWBGroupSpec(
    neurodata_type_def='CatTimeSeries',
    neurodata_type_inc='TimeSeries',
    doc='Categorical data through time',
    datasets=[NWBDatasetSpec(name='data',
                             shape=(None,), dtype='int',
                             doc='timeseries of indicies for values',
                             attributes=[values])])

ns_builder = NWBNamespaceBuilder(doc=namespace + ' extensions', name=namespace,
                                 version='1.0', author='Ben Dichter',
                                 contact='bendichter@gmail.com')
for spec in (cat_cell_info, cat_timeseries):
    ns_builder.add_spec(ext_source, spec)
ns_builder.export(ns_path)
