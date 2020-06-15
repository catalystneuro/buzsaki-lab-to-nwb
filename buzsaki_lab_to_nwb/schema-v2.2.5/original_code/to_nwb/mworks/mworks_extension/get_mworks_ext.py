from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, NWBAttributeSpec
from hdmf.spec import RefSpec
from pynwb import register_class, load_namespaces, NWBFile, NWBHDF5IO, get_class
from hdmf.utils import docval
from pynwb.file import Subject as original_Subject, NWBContainer, MultiContainerInterface


name = 'mworks'
ns_path = name + ".namespace.yaml"
ext_source = name + ".extensions.yaml"

main_screen_info = NWBGroupSpec(
    neurodata_type_def='mainScreenInfo',
    neurodata_type_inc='NWBDataInterface',
    quantity='?',
    doc='',
    attributes=[
        NWBAttributeSpec(name='always_display_mirror_window',
                         doc='doc', dtype='bool', required=False),
        NWBAttributeSpec(name='distance', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='width', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='mirror_window_base_height', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='gammaR', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='redraw_on_every_refresh', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='announce_individual_stimuli', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='height', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='display_to_use', doc='doc', dtype='int', required=False),
        NWBAttributeSpec(name='gammaG', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='refresh_rate_hz', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='gammaB', doc='doc', dtype='float', required=False),
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='settings parameters stored by MWorks')
        ],
)

sound_play = NWBGroupSpec(
    neurodata_type_def='SoundPlay',
    neurodata_type_inc='TimeSeries',
    doc='contains information for sounds played to subject during task. Data represents amplitude',
    datasets=[
        NWBDatasetSpec(name='data', dtype='int', shape=(None,),
                       doc='indexes sound_files and sound_names in attributes',
                       attributes=[
                           NWBAttributeSpec(name='sound_files', doc='indexed by data', dtype='text'),
                           NWBAttributeSpec(name='sound_names', doc='indexed by data', dtype='text')
                       ]),
        NWBDatasetSpec(name='amplitude', dtype='double', shape=(None,),
                       doc='amplitude of sound')
    ],
)

eye_calibrator = NWBGroupSpec(
    neurodata_type_def='EyeCalibration',
    neurodata_type_inc='NWBDataInterface',
    doc='Eye Calibration parameters',
    datasets=[
        NWBDatasetSpec(name='params_V', dtype='double', shape=(6,), doc='vertical parameters'),
        NWBDatasetSpec(name='params_H', dtype='double', shape=(6,), doc='horizontal parameters')
    ]
)

mworks_params = NWBGroupSpec(
    neurodata_type_def='MWorksParams',
    neurodata_type_inc='NWBDataInterface',
    groups=[eye_calibrator, main_screen_info],
    attributes=[NWBAttributeSpec(name='loadedExperiment', dtype='text',
                                 doc='XML storing information about experiment parameters')]
)


ns_builder = NWBNamespaceBuilder(name, name)

specs = (spec,)
for spec in specs:
    ns_builder.add_spec(ext_source, spec)
ns_builder.export(ns_path)

