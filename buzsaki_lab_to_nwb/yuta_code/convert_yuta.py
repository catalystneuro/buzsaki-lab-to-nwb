"""Authors: Cody Baker and Ben Dichter."""
from buzsaki_lab_to_nwb import YutaNWBConverter

# TODO: add pathlib
import os
import pandas as pd
from joblib import Parallel, delayed

n_jobs = 1  # number of parallel streams to run

# List of folder paths to iterate over
base_path = "D:/BuzsakiData/SenzaiY"
# base_path = "/mnt/scrap/cbaker239/SenzaiY"

# Manual list of selected sessions that cause problems with the general functionality
exlude_sessions = ["YutaMouse33-150218"]

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
        session_name = session.stem
        datfile_path = session / f"{session_name}.dat"
        eegfile_path = session / f"{session_name}.eeg"

        source_data = dict(
            YutaLFP=dict(file_path=str(eegfile_path), gain=conversion_factor),
            NeuroscopeSorting=dict(folder_path=str(session), keep_mua_units=False, load_waveforms=True),
            YutaPosition=dict(folder_path=str(session)),
            YutaBehavior=dict(folder_path=str(session))
        )
        conversion_options = dict(
            YutaLFP=dict(stub_test=stub_test),
            NeuroscopeSorting=dict(stub_test=stub_test, write_waveforms=True)
        )
        if datfile_path.is_file():
            source_data.update(NeuroscopeRecording=dict(file_path=str(datfile_path), gain=conversion_factor))
            conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))
        yuta_converter = YutaNWBConverter(source_data)
        metadata = yuta_converter.get_metadata()
        # Yuta specific info
        metadata['NWBFile'].update(
            experimenter=experimenter,
            session_description=paper_descr,
            related_publications=paper_info
        )
        metadata['Subject'].update(species="Mus musculus")
        metadata['Ecephys']['Device'][0].update(name='Implant', description=device_descr)
        for electrode_group_metadata in metadata['Ecephys']['ElectrodeGroup']:
            electrode_group_metadata.update(location="unknown")
            electrode_group_metadata.update(device_name='Implant')
        yuta_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            metadata=metadata,
            conversion_options=conversion_options,
            overwrite=True
        )
    else:
        print(f"The folder ({session}) does not exist!")


Parallel(n_jobs=n_jobs)(delayed(run_yuta_conv)(session, nwbfile_path)
                        for session, nwbfile_path in zip(session_strings, nwbfile_paths)
                        if os.path.split(session)[1] not in exlude_sessions)
