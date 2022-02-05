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

    nwbfile_path = str(base_path / f"{session_id}_stub.nwb")
    raw_data_file_path = session_path / f"{session_id}.dat"
    eeg_file_path = str(session_path / f"{session_id}.lfp")
    spikes_matfile_path = str(session_path / f"{session_id}.spikes.cellinfo.mat")

    mpg_file_paths = [str(session_path / f"{session_id}-04-run.mpg")]

    source_data = dict(
        NeuroscopeLFP=dict(file_path=eeg_file_path, gain=conversion_factor),
        CellExplorerSorting=dict(spikes_matfile_path=spikes_matfile_path),
        GirardeauMisc=dict(folder_path=folder_path),
        MPG=dict(file_paths=mpg_file_paths)
    )
    conversion_options = dict(
        CellExplorerSorting=dict(stub_test=stub_test),
        NeuroscopeLFP=dict(stub_test=stub_test),
        MPG=dict(stub_test=stub_test)
    )
    if raw_data_file_path.is_dir():
        source_data.update(NeuroscopeRecording=dict(file_path=str(raw_data_file_path), gain=conversion_factor))
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test, buffer_mb=2000))
    else:
        conversion_options['CellExplorerSorting'].update(write_ecephys_metadata=True)

    converter = GirardeauNWBConverter(source_data)
    metadata = converter.get_metadata()
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True
    )
