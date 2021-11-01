from pathlib import Path

from buzsaki_lab_to_nwb.yuta_code_visual_cortex.yutavcnwbconverter import YutaVCNWBConverter

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

subject_genotype_dic = dict(
    YMV01="Ai35",
    YMV02="Ai35",
    YMV03="Ai35",
    YMV04="CaMKII-Cre::Ai32",
    YMV05="PV-Cre::Ai32",
    YMV06="VGAT-Cre::Ai32",
    YMV07="CaMKII-Cre::Ai35",
    YMV08="VGAT-Cre::Ai32",
    YMV09="PV-Cre::Ai32",
    YMV10="PV-Cre::Ai32",
    YMV11="PV-Cre::Ai32",
    YMV12="VGAT-Cre::Ai32",
    YMV13="PV-Cre::Ai32",
    YMV14="PV-Cre::Ai32",
    YMV15="PV-Cre::Ai32",
    YMV16="PV-Cre::Ai32",
    YMV17="PV-Cre::Ai32",
    YMV18="PV-Cre::Ai32",
    YMV19="PV-Cre::Ai32",
)


for session_path in session_list[:1]:
    print(f"Processsing {session_path}...")
    session_name = session_path.stem
    subject_name = session_path.parent.name
    dat_file_path = session_path / f"{session_name}.dat"
    eeg_file_path = session_path / f"{session_name}.eeg"
    nwbfile_path = session_path / f"{session_name}.nwb"

    source_data = dict(
        NeuroscopeRecording=dict(file_path=str(dat_file_path), gain=conversion_factor),
        NeuroscopeLFP=dict(file_path=str(eeg_file_path), gain=conversion_factor),
        YutaVCBehavior=dict(folder_path=str(session_path)),
    )

    converter = YutaVCNWBConverter(source_data=source_data)

    conversion_options = dict(
        NeuroscopeRecording=dict(stub_test=stub_test),
        NeuroscopeLFP=dict(stub_test=stub_test),
    )

    # Update metadata
    metadata = converter.get_metadata()
    metadata["Subject"].update(genotype=subject_genotype_dic[subject_name])

    converter.run_conversion(
        nwbfile_path=str(nwbfile_path), conversion_options=conversion_options, metadata=metadata, overwrite=True
    )
