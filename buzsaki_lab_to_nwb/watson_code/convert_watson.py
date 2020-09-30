"""Authors: Cody Baker and Ben Dichter."""
from buzsaki_lab_to_nwb import YutaNWBConverter
# TODO: add pathlib
import os

# List of folder paths to iterate over
experimenter = "Brendon Watson"
base_path = "D:/BuzsakiData/WatsonBO"
convert_sessions = ["BWRat17-121712", "BWRat17-121912", "BWRat18-020513", "BWRat19-032513", "BWRat19-032413",
                    "BWRat20-101013", "BWRat20-101513", "BWRat21-121113", "BWRat21-121613", "BWRat21-121813"]

paper_descr = "Data was recorded using silicon probe electrodes in the frontal cortices of male Long " \
              "Evans rats between 4-7 months of age. The design was to have no specific behavior, " \
              "task or stimulus, rather the animal was left alone in it’s home cage (which it lives in at all " \
              "times)."
paper_info = "Network Homeostasis and State Dynamics of Neocortical Sleep" \
             "Watson BO, Levenstein D, Greene JP, Gelinas JN, Buzsáki G." \
             "Neuron. 2016 Apr 27. pii: S0896-6273(16)30056-3." \
             "doi: 10.1016/j.neuron.2016.03.036"

for j, session in enumerate(convert_sessions):
    # TODO: replace with pathlib
    session_id = os.path.split(session)[1]

    input_file_schema = YutaNWBConverter.get_input_schema()

    # construct input_args dict according to input schema
    input_args = {
        'NeuroscopeRecording': {'file_path': os.path.join(session, session_id) + ".dat"},
        'NeuroscopeSorting': {'folder_path': session,
                              'keep_mua_units': False},
        'WatsonLFP': {'folder_path': session},
        'WatsonBehavior': {'folder_path': session}
    }

    yuta_converter = YutaNWBConverter(**input_args)

    expt_json_schema = yuta_converter.get_metadata_schema()

    # construct metadata_dict according to expt_json_schema
    metadata = yuta_converter.get_metadata()

    # Yuta specific info
    metadata['NWBFile'].update({'experimenter': experimenter})
    metadata['NWBFile'].update({'session_description': paper_descr})
    metadata['NWBFile'].update({'related_publications': paper_info})

    metadata['Subject'].update({'species': 'Rat'})
    metadata['Subject'].update({'strain': 'Long Evans'})
    metadata['Subject'].update({'genotype': 'Wild type'})
    metadata['Subject'].update({'age': '3-7 months'})  # No age data avilable per subject without contacting lab
    metadata['Subject'].update({'weight': '250-500g'})

    device_descr = "silicon probe electrodes; see {}.xml or {}.sessionInfo.mat for more information".format(session_id,
                                                                                                            session_id)
    metadata[yuta_converter.get_recording_type()]['Ecephys']['Device'][0].update({'description': device_descr})

    nwbfile_path = session + "_stub.nwb"
    yuta_converter.run_conversion(nwbfile_path, metadata, stub_test=True)
