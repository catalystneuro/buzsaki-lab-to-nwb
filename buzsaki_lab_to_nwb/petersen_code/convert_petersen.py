"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

from buzsaki_lab_to_nwb import PetersenNWBConverter

base_path = Path("E:/BuzsakiData/PetersenP")
# base_path = Path("/mnt/scrap/cbaker239/PetersenP")  # for smaug

exclude_mice = ["MS12"]
convert_sessions = [
    session
    for mouse in base_path.iterdir()
    if mouse.is_dir() and mouse.name not in exclude_mice
    for session in mouse.iterdir()
]

# Weights retrieved from Buzsaki website
subject_weight = dict(MS10=395, MS12=410, MS13=320, MS21=250, MS22=260)

stub_test = True
conversion_factor = 0.195  # Intan

for session_path in convert_sessions:
    folder_path = str(session_path)
    subject_name = session_path.parent.name
    session_id = session_path.name
    print(f"Converting session {session_id}...")

    nwbfile_path = str((base_path / f"{session_id}_stub.nwb"))

    # There is a potentially useful amplifier.xml file, so need to specify which to use for other recordings
    xml_file_path = str(session_path / f"{session_id}.xml")
    lfp_file_path = str(session_path / f"{session_id}.lfp")
    raw_data_file_path = session_path / f"{session_id}.dat"

    source_data = dict(
        NeuroscopeLFP=dict(
            file_path=lfp_file_path, gain=conversion_factor, xml_file_path=xml_file_path
        ),
        PetersenMisc=dict(folder_path=folder_path),
    )
    conversion_options = dict(NeuroscopeLFP=dict(stub_test=stub_test))
    if raw_data_file_path.is_file():
        source_data.update(
            NeuroscopeRecording=dict(
                file_path=str(raw_data_file_path),
                gain=conversion_factor,
                xml_file_path=xml_file_path,
            )
        )
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))

    # Sessions contain either no sorting data of any kind, Phy format, or incomplete CellExplorer format
    kilo_dirs = [
        x for x in session_path.iterdir() if x.is_dir() and "Kilosort" in x.name
    ]
    if len(kilo_dirs) == 1:
        source_data.update(PhySorting=dict(folder_path=str(kilo_dirs[0])))
        conversion_options.update(PhySorting=dict(stub_test=stub_test))

    converter = PetersenNWBConverter(source_data)
    metadata = converter.get_metadata()
    metadata["Subject"].update(weight=f"{subject_weight[subject_name]}g")
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
