from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, NWBAttributeSpec
from hdmf.spec import RefSpec
from pynwb import register_class, load_namespaces, NWBFile, NWBHDF5IO, get_class
from hdmf.utils import docval
from pynwb.file import Subject as original_Subject, NWBContainer, MultiContainerInterface


namespace = 'time_frequency'
ns_path = namespace + ".namespace.yaml"
ext_source = namespace + ".extensions.yaml"

spec = NWBGroupSpec(
    neurodata_type_def='HilbertSeries',
    neurodata_type_inc='ElectricalSeries',
    quantity='?',
    doc='output of hilbert transform',
    attributes=[
        NWBAttributeSpec(name='unit',
                         doc='unit',
                         dtype='text',
                         value='no units'),
        NWBAttributeSpec(name='help',
                         doc='help',
                         dtype='text',
                         value='ENTER HELP INFO HERE')],
    datasets=[
        NWBDatasetSpec(name='filter_centers',
                       doc='in Hz',
                       dtype='float',
                       shape=(None,)),
        NWBDatasetSpec(name='filter_sigmas',
                       doc='in Hz',
                       dtype='float',
                       shape=(None,)),
        NWBDatasetSpec(
            name='data',
            doc='Analytic amplitude of signal',
            dtype='float',
            shape=(None, None, None),
            dims=('time', 'channel', 'frequency'),
            quantity='?'),
        NWBDatasetSpec(
            name='real_data',
            doc='The real component of the complex result of the hilbert transform',
            dtype='float',
            shape=(None, None, None),
            dims=('time', 'channel', 'frequency'),
            quantity='?'),
        NWBDatasetSpec(
            name='imaginary_data',
            doc='The imaginary component of the complex result of the hilbert transform',
            dtype='float',
            shape=(None, None, None),
            dims=('time', 'channel', 'frequency'),
            quantity='?'),
        NWBDatasetSpec(
            name='phase_data',
            doc='The phase of the complex result of the hilbert transform',
            dtype='float',
            shape=(None, None, None),
            dims=('time', 'channel', 'frequency'),
            quantity='?')
    ]
)


ns_builder = NWBNamespaceBuilder(doc=namespace + ' extensions', name=namespace,
                                 version='1.0', author='Ben Dichter',
                                 contact='bendichter@gmail.com')
specs = (spec,)
for spec in specs:
    ns_builder.add_spec(ext_source, spec)
ns_builder.export(ns_path)

