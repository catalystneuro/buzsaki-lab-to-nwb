from pynwb.spec import NWBDatasetSpec, NWBNamespaceBuilder, NWBGroupSpec, NWBAttributeSpec

namespace = 'ecog'
ns_path = namespace + ".namespace.yaml"
ext_source = namespace + ".extensions.yaml"

surface = NWBGroupSpec(
    neurodata_type_def='Surface',
    neurodata_type_inc='NWBDataInterface',
    quantity='+',
    doc='brain cortical surface',
    datasets=[  # set Faces and Vertices as elements of the Surfaces neurodata_type
        NWBDatasetSpec(
            doc='faces for surface, indexes vertices', shape=(None, 3),
            name='faces', dtype='uint', dims=('face_number', 'vertex_index')),
        NWBDatasetSpec(
            doc='vertices for surface, points in 3D space', shape=(None, 3),
            name='vertices', dtype='float', dims=('vertex_number', 'xyz'))],
    attributes=[
        NWBAttributeSpec(
            name='help', dtype='text', doc='help',
            value='This holds Surface objects')
    ]
)

surfaces = NWBGroupSpec(
    neurodata_type_def='CorticalSurfaces',
    neurodata_type_inc='NWBDataInterface',
    name='cortical_surfaces',
    doc='triverts for cortical surfaces', quantity='?',
    groups=[surface],
    attributes=[NWBAttributeSpec(
        name='help', dtype='text', doc='help',
        value='This holds the vertices and faces for the cortical surface '
              'meshes')])

ns_builder = NWBNamespaceBuilder(doc=namespace + ' extensions', name=namespace,
                                 version='1.0', author='Ben Dichter',
                                 contact='bendichter@gmail.com')
ns_builder.add_spec(ext_source, surfaces)
ns_builder.export(ns_path)
