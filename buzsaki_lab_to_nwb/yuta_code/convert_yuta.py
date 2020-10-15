"""Authors: Cody Baker and Ben Dichter."""
from buzsaki_lab_to_nwb import YutaNWBConverter

# TODO: add pathlib
import os
import pandas as pd
from joblib import Parallel, delayed

n_jobs = 4  # number of parallel streams to run

# List of folder paths to iterate over
base_path = "D:/BuzsakiData/SenzaiY"
# base_path = "/mnt/scrap/cbaker239/SenzaiY"
paper_sessions = pd.read_excel(os.path.join(base_path, "DGProject/DG_all_6_SessionShankList.xls"), header=None)[0]
sessions = dict()
for paper_session in paper_sessions:
    mouse_id = paper_session[9:11]  # could be generalized better
    if mouse_id in sessions:
        sessions[mouse_id].append(paper_session[11:])
    else:
        sessions.update({mouse_id: [paper_session[11:]]})

experimenter = "Yuta Senzai"
paper_descr = "mouse in open exploration and theta maze"
paper_info = "DOI:10.1016/j.neuron.2016.12.011"

session_strings = []
nwbfile_paths = []
for mouse_num, session_ids in sessions.items():
    for session_id in session_ids:
        # TODO: replace with pathlib
        mouse_str = "YutaMouse" + str(mouse_num)
        session_strings.append(os.path.join(base_path, mouse_str+str(session_id)))
        nwbfile_paths.append(session_strings[-1] + "_stub.nwb")


def run_yuta_conv(session, nwbfile_path):
    """Conversion function to be run in parallel."""
    if os.path.exists(session):
        print(f"Processsing {session}...")
        if not os.path.isfile(nwbfile_path):
            session_name = os.path.split(session)[1]

            # construct input_args dict according to input schema
            input_args = dict(
                source_data=dict(
                    NeuroscopeRecording=dict(file_path=os.path.join(session, session_name) + ".dat"),
                    NeuroscopeSorting=dict(
                        folder_path=session,
                        keep_mua_units=False,
                        exclude_shanks=None
                    ),
                    YutaPosition=dict(folder_path=session),
                    YutaLFP=dict(folder_path=session),
                    YutaBehavior=dict(folder_path=session)
                )
            )

            yuta_converter = YutaNWBConverter(**input_args)

            # construct metadata_dict according to expt_json_schema
            metadata = yuta_converter.get_metadata()

            # Yuta specific info
            metadata['NWBFile'].update({'experimenter': experimenter})
            metadata['NWBFile'].update({'session_description': paper_descr})
            metadata['NWBFile'].update({'related_publications': paper_info})

            metadata['Subject'].update({'species': "Mus musculus"})

            metadata[yuta_converter.get_recording_type()]['Ecephys']['Device'][0].update({'name': 'implant'})

            for electrode_group_metadata in \
                    metadata[yuta_converter.get_recording_type()]['Ecephys']['ElectrodeGroup']:
                electrode_group_metadata.update({'location': 'unknown'})
                electrode_group_metadata.update({'device_name': 'implant'})

            yuta_converter.run_conversion(nwbfile_path=nwbfile_path, metadata_dict=metadata,
                                          stub_test=True, save_to_file=True)
    else:
        print(f"The folder ({session}) does not exist!")


Parallel(n_jobs=n_jobs)(delayed(run_yuta_conv)(session, nwbfile_path)
                         for session, nwbfile_path in zip(session_strings, nwbfile_paths))
