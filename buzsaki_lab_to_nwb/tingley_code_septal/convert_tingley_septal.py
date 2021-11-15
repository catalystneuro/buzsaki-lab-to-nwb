from pathlib import Path

from buzsaki_lab_to_nwb import TingleySeptalNWBConverter

stub_test = True
conversion_factor = 0.195  # Intan
data_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/")
nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwbfiles")

subject_test = "DT5"  # Just for testing

session_list = [
    session
    for subject in data_path.iterdir()
    if subject.is_dir() and subject.name == subject_test
    for session in subject.iterdir()
    if session.is_dir()
]


for session_path in session_list:
    session_id = session_path.name
    lfp_file_path = str(session_path / f"{session_path.name}.lfp")
    nwbfile_path = str((nwb_output_path / f"{session_id}_stub.nwb"))

    source_data = dict(
        NeuroscopeLFP=dict(file_path=lfp_file_path, gain=conversion_factor),
    )

    conversion_options = dict(NeuroscopeLFP=dict(stub_test=stub_test))

    converter = TingleySeptalNWBConverter(source_data)
    metadata = None
    # metadata = converter.get_metadata()
    # metadata["Subject"].update(weight=f"{subject_weight[subject_name]}g")
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
