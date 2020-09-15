"""Authors: Cody Baker and Ben Dichter."""
from yutanwbconverter import YutaNWBConverter
# TODO: add pathlib
import os

# List of folder paths to iterate over
convert_sessions = [#"D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903",
                    "D:/BuzsakiData/SenzaiY/YutaMouse20/YutaMouse20-140225",
                    "D:/BuzsakiData/SenzaiY/YutaMouse55/YutaMouse55-160907"]

session_descriptions = [#"mouse in open exploration and theta maze",
                        "mouse in open exploration and theta maze",
                        "mouse in open exploration and theta maze"]

# Session specific info
n_sessions = len(convert_sessions)
session_specific_metadata = [{}] * n_sessions
for j in range(n_sessions):
    session_specific_metadata[j]['NWBFile'] = {}
    session_specific_metadata[j]['NWBFile'].update({'session_description': session_descriptions[j]})
# session_specific_metadata[0]['NWBFile'].update({'related_publications': 'DOI:10.1016/j.neuron.2016.12.011'})

for j, session in enumerate(convert_sessions):
    # TODO: replace with pathlib
    session_name = os.path.split(session)[1]

    input_file_schema = YutaNWBConverter.get_input_schema()

    # construct input_args dict according to input schema
    input_args = {
        'NeuroscopeRecording': {'file_path': os.path.join(session, session_name) + ".dat"},
        'NeuroscopeSorting': {'folder_path': session,
                              'keep_mua_units': False},
        'YutaPosition': {'folder_path': session},
        'YutaLFP': {'folder_path': session},
        'YutaBehavior': {'folder_path': session}
    }

    yuta_converter = YutaNWBConverter(**input_args)

    expt_json_schema = yuta_converter.get_metadata_schema()

    # expt_json_schema does not indicate device linking in ElectrodeGroup.
    # Also out of place 'type' in property levels?

    # construct metadata_dict according to expt_json_schema
    metadata = yuta_converter.get_metadata()

    # TODO: better way to nest smart dictionary updates?
    for key1, val1 in session_specific_metadata[j].items():
        if type(val1) is dict:
            for key2, val2 in val1.items():
                metadata[key1].update({key2: val2})
        else:
            metadata.update({key1: val1})

    # Yuta specific info
    metadata['NWBFile'].update({'experimenter': 'Yuta Senzai'})

    metadata[yuta_converter.get_recording_type()]['Ecephys']['Device'][0].update({'name': 'implant'})

    for electrode_group_metadata in metadata[yuta_converter.get_recording_type()]['Ecephys']['ElectrodeGroup']:
        electrode_group_metadata.update({'location': 'unknown'})
        electrode_group_metadata.update({'device_name': 'implant'})

    nwbfile_path = session + "_new_converter.nwb"
    yuta_converter.run_conversion(nwbfile_path, metadata, stub_test=True)
