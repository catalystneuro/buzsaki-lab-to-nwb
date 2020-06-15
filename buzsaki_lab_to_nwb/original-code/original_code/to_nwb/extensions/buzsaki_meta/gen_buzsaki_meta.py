from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, NWBAttributeSpec
from hdmf.spec import RefSpec
from pynwb import register_class, load_namespaces, NWBFile, NWBHDF5IO
from hdmf.utils import docval
from pynwb.file import Subject, NWBContainer, MultiContainerInterface, NWBDataInterface
from pynwb.device import Device



from datetime import datetime
from dateutil.parser import parse as parse_date

import re


namespace = 'buzsaki_meta'
ns_path = namespace + ".namespace.yaml"
ext_source = namespace + ".extensions.yaml"


manipulation = NWBGroupSpec(
    neurodata_type_def='Manipulation',
    neurodata_type_inc='NWBDataInterface',
    quantity='+',
    doc='manipulation',
    attributes=[
        NWBAttributeSpec(name='brain_region_target', dtype='text', doc='Allan Institute Acronym')
    ]
)


virus_injection = NWBGroupSpec(
    neurodata_type_inc='NWBDataInterface',
    neurodata_type_def='VirusInjection', quantity='+',
    doc='notes about surgery that includes virus injection',
    datasets=[NWBDatasetSpec(name='coordinates', doc='(AP, ML, DV) of virus injection',
                             dtype='float', shape=(3,))],
    attributes=[
        NWBAttributeSpec(name='virus', doc='type of virus', dtype='text'),
        NWBAttributeSpec(name='volume', doc='volume of injecting in nL', dtype='float'),
        NWBAttributeSpec(name='rate', doc='rate of injection (nL/s)',
                         dtype='float', required=False),
        NWBAttributeSpec(name='scheme', doc='scheme of injection', dtype='text', required=False),
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Information about a virus injection')])

virus_injections = NWBGroupSpec(
    neurodata_type_def='VirusInjections',
    neurodata_type_inc='NWBDataInterface',
    name='virus_injections',
    doc='stores virus injections', quantity='?',
    groups=[virus_injection],
    attributes=[
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Container for virus injections')
    ])

manipulations = NWBGroupSpec(
    neurodata_type_def='Manipulations',
    neurodata_type_inc='NWBDataInterface',
    name='manipulations',
    doc='stores maipulations', quantity='?',
    groups=[manipulation])


surgery = NWBGroupSpec(
    neurodata_type_def='Surgery', doc='information about a specific surgery', quantity='+',
    neurodata_type_inc='NWBDataInterface',
    datasets=[NWBDatasetSpec(name='devices', quantity='?', doc='links to implanted/explanted devices',
                             dtype=RefSpec('Device', 'object'))],
    groups=[virus_injections, manipulations],
    attributes=[
        NWBAttributeSpec(name='start_datetime', doc='datetime in ISO 8601', dtype='text', required=False),
        NWBAttributeSpec(name='end_datetime', doc='datetime in ISO 8601', dtype='text', required=False),
        NWBAttributeSpec(name='weight', required=False, dtype='text',
                         doc='Weight at time of experiment, at time of surgery and at other '
                             'important times'),
        NWBAttributeSpec(name='notes', doc='notes and complications', dtype='text', required=False),
        NWBAttributeSpec(name='anesthesia', doc='anesthesia', dtype='text', required=False),
        NWBAttributeSpec(name='analgesics', doc='analgesics', dtype='text', required=False),
        NWBAttributeSpec(name='antibiotics', doc='antibiotics', dtype='text', required=False),
        NWBAttributeSpec(name='complications', doc='complications', dtype='text', required=False),
        NWBAttributeSpec(name='target_anatomy', doc='target anatomy', dtype='text', required=False),
        NWBAttributeSpec(name='room', doc='place where the surgery took place', dtype='text',
                         required=False),
        NWBAttributeSpec(name='surgery_type', doc='"chronic" or "acute"', dtype='text', required=False),
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Information about surgery')
    ])

surgeries = NWBGroupSpec(
    neurodata_type_def='Surgeries',
    neurodata_type_inc='NWBDataInterface',
    name='surgeries',
    doc='relevant data for surgeries', quantity='?',
    groups=[surgery],
    attributes=[
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Container for surgeries')
    ])

histology = NWBGroupSpec(
    neurodata_type_def='Histology',
    neurodata_type_inc='NWBDataInterface',
    name='histology',
    doc='information about histology of subject',
    quantity='?',
    attributes=[
        NWBAttributeSpec(name='file_name', doc='filename of histology images', dtype='text'),
        NWBAttributeSpec(name='file_name_ext', doc='filename extension', dtype='text'),
        NWBAttributeSpec(name='imaging_technique',
                         doc='histology imaging technique (e.g. widefield, confocal, etc.)',
                         dtype='text'),
        NWBAttributeSpec(name='slice_plane', doc='[Coronal, Sagital, Transverse, Other]',
                         required=False, dtype='text'),
        NWBAttributeSpec(name='slice_thickness', doc='thickness of slice (um)', dtype='float',
                         required=False),
        NWBAttributeSpec(name='location_along_axis', doc='Axis orthogal to SlicePlane (mm)',
                         dtype='float', required=False),
        NWBAttributeSpec(name='brain_region_target', doc='Allen Institute acronym',
                         dtype='text', required=False),
        NWBAttributeSpec(name='stainings', doc='stainings', dtype='text', required=False),
        NWBAttributeSpec(name='light_source', doc='wavelength of light source in nm',
                         dtype='float', required=False),
        NWBAttributeSpec(name='image_scale', doc='scale of image (pixels/100um)', dtype='float',
                         required=False),
        NWBAttributeSpec(name='scale_bar', doc='size of image scale bar (um)', dtype='float',
                         required=False),
        NWBAttributeSpec(name='post_processing', doc='[Z-stacked, Stiched]', dtype='text',
                         required=False),
        NWBAttributeSpec(name='user', doc='person involved', dtype='text', required=False),
        NWBAttributeSpec(name='notes', doc='anything else', dtype='text', required=False),
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Information about Histology')
    ])


subject = NWBGroupSpec(
    neurodata_type_inc='Subject',
    neurodata_type_def='BuzSubject',
    name='subject',
    doc='information about subject',
    groups=[surgeries, histology],
    attributes=[
        NWBAttributeSpec(
            name='sex', required=False, dtype='text',
            doc='Sex of subject. Options: "M": male, "F": female, "O": other, "U": unknown'),
        NWBAttributeSpec(name='species', doc='Species of subject', dtype='text', required=False),
        NWBAttributeSpec(name='strain', dtype='text', doc='strain of animal', required=False),
        NWBAttributeSpec(name='genotype', dtype='text', doc='genetic line of animal', required=False),
        NWBAttributeSpec(name='date_of_birth', dtype='text', doc='in ISO 8601 format', required=False),
        NWBAttributeSpec(name='date_of_death', dtype='text', doc='in ISO 8601 format', required=False),
        NWBAttributeSpec(name='age', doc='age of subject. No specific format enforced.', dtype='text',
                         required=False),
        NWBAttributeSpec(name='gender', dtype='text', required=False,
                         doc='Gender of subject if different from sex.'),
        NWBAttributeSpec(name='earmark', dtype='text', required=False,
                         doc='Earmark of subject'),
        NWBAttributeSpec(name='weight', required=False, dtype='text',
                         doc='Weight at time of experiment, at time of surgery in grams'),
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Buzsaki subject structure')
    ])

probe = NWBGroupSpec(
    neurodata_type_inc='Device',
    neurodata_type_def='Probe',
    name='probe',
    doc='probe',
    datasets=[
        NWBDatasetSpec(name='coordinates', doc='(AP, ML, DV) of virus injection',
                       dtype='float', shape=(3,)),
        NWBDatasetSpec(name='angles', doc='(degrees) [AP,MD,DV]', dtype='float', shape=(3,))

    ],
    attributes=[
        NWBAttributeSpec(name='nchannels', dtype='int', doc='number of channels'),
        NWBAttributeSpec(name='spike_groups', dtype='int', doc='spike groups'),
        NWBAttributeSpec(name='wire_count', dtype='int', doc='wire count'),
        NWBAttributeSpec(name='write_diameter', dtype='float', doc='diameter of wire'),
        NWBAttributeSpec(name='rotation', dtype='float', doc='rotation of probe'),
        NWBAttributeSpec(name='ground_electrode', dtype='text', doc='e.g. "screw above cerebellum"'),
        NWBAttributeSpec(name='reference_electrode', dtype='text', doc='e.g. "shorted to ground"')
    ]
)

silicon_probe = NWBGroupSpec(
    neurodata_type_inc='Probe',
    neurodata_type_def='SiliconProbe',
    doc='silicon probe',
    attributes=[
        NWBAttributeSpec(name='probe_id', dtype='text', doc='probe id')
    ]
)

tetrode = NWBGroupSpec(
    neurodata_type_inc='Probe',
    neurodata_type_def='Tetrode',
    doc='tetrode',
    attributes=[
        NWBAttributeSpec(name='tetrode_count', dtype='int', doc='number of tetrodes')
    ]
)

optical_fiber = NWBGroupSpec(
    neurodata_type_inc='Device',
    neurodata_type_def='OpticalFiber',
    name='OpticalFiber',
    doc='Meta-data about optical fiber',
    attributes=[
        NWBAttributeSpec(name='type', doc='model', dtype='text', required=False),
        NWBAttributeSpec(name='core_diameter', doc='in um', dtype='float', required=False),
        NWBAttributeSpec(name='outer_diameter', doc='in um', dtype='float', required=False),
        NWBAttributeSpec(name='microdrive', doc='whether a microdrive was used (0: not used, 1: used)',
                         dtype='int'),
        NWBAttributeSpec(name='microdrive_lead', doc='um/turn', dtype='float', required=False),
        NWBAttributeSpec(name='microdrive_id', doc='id of microdrive', dtype='int', required=False),
        NWBAttributeSpec(name='help', doc='help', dtype='text', value='Information about optical fiber')
    ]
)

ns_builder = NWBNamespaceBuilder(doc=namespace + ' extensions', name=namespace,
                                 version='1.0', author='Ben Dichter',
                                 contact='bendichter@gmail.com')

specs = (subject, optical_fiber)
for spec in specs:
    ns_builder.add_spec(ext_source, spec)
ns_builder.export(ns_path)


