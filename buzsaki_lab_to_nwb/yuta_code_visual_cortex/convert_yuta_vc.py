from pathlib import Path

from buzsaki_lab_to_nwb.yuta_code_visual_cortex.yutanwbconverter_vc import YutaVCNWBConverter

data_path = Path("/home/heberto/globus_data")
author_path = Path("SenzaiY")
base_path = data_path.joinpath(author_path)

stub_test = True
conversion_factor = 0.195  # Intan

session_list = [
    session
    for subject in base_path.iterdir()
    if subject.is_dir() and "YMV" in subject.name
    for session in subject.iterdir()
]
session_list = [session for session in session_list if session.is_dir()]


for session in session_list:
    print(f"Processsing {session}...")
    session_name = session.stem
    dat_file_path = session / f"{session_name}.dat"
    eeg_file_path = session / f"{session_name}.eeg"
    nwbfile_path = session / f"{session_name}.nwb"

    source_data = dict(
        NeuroscopeRecording=dict(file_path=str(dat_file_path), gain=conversion_factor),
        NeuroscopeLFP=dict(file_path=str(eeg_file_path), gain=conversion_factor),
    )

    # Missing behaviors

    # Missing meta data

    converter = YutaVCNWBConverter(source_data=source_data)

    conversion_options = dict(
        NeuroscopeRecording=dict(stub_test=stub_test),
        NeuroscopeLFP=dict(stub_test=stub_test),
    )

    converter.run_conversion(nwbfile_path=str(nwbfile_path), conversion_options=conversion_options, overwrite=True)
