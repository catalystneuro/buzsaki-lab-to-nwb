"""Authors: Cody Baker and Ben Dichter."""
from buzsaki_lab_to_nwb import WatsonNWBConverter
# TODO: add pathlib
import os

# List of folder paths to iterate over
base_path = "D:/BuzsakiData/WatsonBO"
convert_sessions = [#"BWRat17/BWRat17_121712", "BWRat17/BWRat17_121912", "BWRat18/BWRat18_020513",
                    #"BWRat19/BWRat19_032513", "BWRat19/BWRat19_032413", "BWRat20/BWRat20_101013",
                    #"BWRat20/BWRat20_101513", "BWRat21/BWRat21_121113", "BWRat21/BWRat21_121613",
                    #"BWRat21/BWRat21_121813", "Bogey/Bogey_012615",
                    #"Dino/Dino_061814",
                    #"Dino/Dino_061914",
                    "Dino/Dino_062014",  # incorrect # of channels for full lfp reshaping...
                    #"Dino/Dino_072114"#, # missing clu files...
                    #"Dino/Dino_072314", "Dino/Dino_072414", "Rizzo/Rizzo_022615",
                    #"Rizzo/Rizzo_022715",
                    #"Splinter/Splinter_020515", "Splinter/Splinter_020915",
                    #"Templeton/Templeton_032415"
                    ]

experimenter = "Brendon Watson"
paper_descr = "Data was recorded using silicon probe electrodes in the frontal cortices of male Long " \
              "Evans rats between 4-7 months of age. The design was to have no specific behavior, " \
              "task or stimulus, rather the animal was left alone in it’s home cage (which it lives in at all " \
              "times)."
paper_info = "Network Homeostasis and State Dynamics of Neocortical Sleep" \
             "Watson BO, Levenstein D, Greene JP, Gelinas JN, Buzsáki G." \
             "Neuron. 2016 Apr 27. pii: S0896-6273(16)30056-3." \
             "doi: 10.1016/j.neuron.2016.03.036"

for session in convert_sessions:
    print("Converting session {}...".format(session))

    # TODO: replace with pathlib
    session_id = os.path.split(session)[1]
    folder_path = os.path.join(base_path, session)

    input_file_schema = WatsonNWBConverter.get_input_schema()

    # construct input_args dict according to input schema
    input_args = {
        'NeuroscopeRecording': {'file_path': os.path.join(folder_path, session_id) + ".dat"},
        'WatsonLFP': {'folder_path': folder_path},
        'WatsonBehavior': {'folder_path': folder_path}
    }

    # Very special case
    if session == "Dino/Dino_072114":
        input_args.update({'CellExplorerSorting': {'spikes_file_path': os.path.join(folder_path, session_id)
                                                   + ".spikes.cellinfo.mat"}})
    else:
        input_args.update({'NeuroscopeSorting': {'folder_path': folder_path,
                                                 'keep_mua_units': False}})

    watson_converter = WatsonNWBConverter(**input_args)

    expt_json_schema = watson_converter.get_metadata_schema()

    # construct metadata_dict according to expt_json_schema
    metadata = watson_converter.get_metadata()

    # Yuta specific info
    metadata['NWBFile'].update({'experimenter': experimenter})
    metadata['NWBFile'].update({'session_description': paper_descr})
    metadata['NWBFile'].update({'related_publications': paper_info})

    metadata['Subject'].update({'species': 'Rattus norvegicus domestica - Long Evans'})
    metadata['Subject'].update({'genotype': 'Wild type'})
    metadata['Subject'].update({'age': '3-7 months'})  # No age data avilable per subject without contacting lab
    metadata['Subject'].update({'weight': '250-500g'})

    device_descr = "silicon probe electrodes; see {}.xml or {}.sessionInfo.mat for more information".format(session_id,
                                                                                                            session_id)
    metadata[watson_converter.get_recording_type()]['Ecephys']['Device'][0].update({'description': device_descr})

    nwbfile_path = os.path.join(folder_path, "{}.nwb".format(session_id))
    watson_converter.run_conversion(nwbfile_path, metadata, stub_test=False)
