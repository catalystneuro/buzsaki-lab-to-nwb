"""Authors: Cody Baker and Ben Dichter."""
from buzsaki_lab_to_nwb import YutaNWBConverter

# TODO: add pathlib
import os

# List of folder paths to iterate over
base_path = "D:/BuzsakiData/WatsonBO"
convert_sessions = ["BWRat17-121712", "BWRat17-121912", "BWRat18-020513", "BWRat19-032513", "BWRat19-032413",
                    "BWRat20-101013", "BWRat20-101513", "BWRat21-121113", "BWRat21-121613", "BWRat21-121813"]

paper_descr = "Data was recorded using silicon probe electrodes in the frontal cortices of male Long " \
              "Evans rats between 4-7 months of age. The design was to have no specific behavior, " \
              "task or stimulus, rather the animal was left alone in it’s home cage (which it lives in at all " \
              "times)."
session_descriptions = [paper_descr for x in range(len(convert_sessions))]

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
