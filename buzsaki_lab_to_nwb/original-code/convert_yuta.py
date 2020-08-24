
import BuzsakiLabNWBConverter as Buz2Nwb

# usage
input_file_schema = Buz2Nwb.BuzsakiLabNWBConverter.get_input_schema()

# construct input_args dict according to input schema, e.g.: 
input_args = {
    'NeuroscopeRecording': {'file_path': "D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903/YutaMouse41-150903.dat"},
    'NeuroscopeSorting': {'folder_path': "D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903", 
                          'keep_mua_units': False},
    'BuzsakiLabBehavioral': {'folder_path': "D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903"}
}

buzlab_converter = Buz2Nwb.BuzsakiLabNWBConverter(**input_args)

expt_json_schema = buzlab_converter.get_metadata_schema()

# expt_json_schema does not indicate device linking in ElectrodeGroup.
# Also out of place 'type' in property levels?


# construct metadata_dict according to expt_json_schema
metadata_dict = buzlab_converter.get_metadata()


# Yuta specific modification
metadata_dict['NWBFile'].update({'session_description': 'mouse in open exploration and theta maze'})
metadata_dict['NWBFile'].update({'experimenter': 'Yuta Senzai'})
metadata_dict['NWBFile'].update({'related_publications': 'DOI:10.1016/j.neuron.2016.12.011'})

metadata_dict['NeuroscopeRecording']['Ecephys']['Device'][0].update({'name': 'implant'})

for electrode_group_metadata in metadata_dict['NeuroscopeRecording']['Ecephys']['ElectrodeGroup']:
    electrode_group_metadata.update({'location': 'unknown'})
    electrode_group_metadata.update({'device_name': 'implant'})

metadata_dict['BuzsakiLabBehavioral'].update({'task_types': [
    {'name': 'OpenFieldPosition_ExtraLarge'},
    {'name': 'OpenFieldPosition_New_Curtain', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_New', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_Old_Curtain', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_Old', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_Oldlast', 'conversion': 0.46},
    {'name': 'EightMazePosition', 'conversion': 0.65 / 2}
]})
    

nwbfile_path = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903_new_converter.nwb'
buzlab_converter.run_conversion(nwbfile_path, metadata_dict, stub_test=True)
