"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

from buzsaki_lab_to_nwb import GirardeauNWBConverter

base_path = Path("D:/BuzsakiData/GirardeauG")
convert_sessions = [session for mouse in base_path.iterdir() if mouse.is_dir() for session in mouse.iterdir()]

stub_test = True
conversion_factor = 0.3815  # Ampliplex

for session_path in convert_sessions:
    folder_path = str(session_path)
    subject_name = session_path.parent.name
    session_id = session_path.name
    print(f"Converting session {session_id}...")

    eeg_file_path = str((session_path / f"{session_id}.eeg"))
    spikes_matfile_path = str((session_path / f"{session_id}.spikes.cellinfo.mat"))
    raw_data_folder_path = session_path / "raw"

    source_data = dict(
        CellExplorerSorting=dict(spikes_matfile_path=spikes_matfile_path),
        NeuroscopeLFP=dict(file_path=eeg_file_path, gain=conversion_factor),
        # PeyracheBehavior=dict(folder_path=folder_path)
    )
    conversion_options = dict(
        CellExplorerSorting=dict(stub_test=stub_test),
        NeuroscopeLFP=dict(stub_test=stub_test)
    )
    if raw_data_folder_path.is_dir():
        folder_path = str(raw_data_folder_path)
        source_data.update(
            NeuroscopeRecording=dict(folder_path=folder_path, gain=conversion_factor)
        )
        conversion_options.update(
            NeuroscopeRecording=dict(stub_test=stub_test)
        )
    else:
        conversion_options['CellExplorerSorting'].update(write_ecephys_metadata=True)

    converter = GirardeauNWBConverter(source_data)
    metadata = converter.get_metadata()
    nwbfile_path = str((base_path / f"{session_id}_stub.nwb"))
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True
    )
