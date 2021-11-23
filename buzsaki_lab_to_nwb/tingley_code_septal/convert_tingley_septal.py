from pathlib import Path

from buzsaki_lab_to_nwb import TingleySeptalNWBConverter

stub_test = True
conversion_factor = 0.195  # Intan
data_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/")
nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwbfiles")

subject_list = ["DT2", "DT5", "DT7", "DT8", "DT9"]
# subject_list = ['DT5']

invalid_session = [
    "20170411_1296um_1152um_170411_113418",  # No data
    "20170527_1260um_1072um_merge",  # No data
    "20170528_1332um_1108um_170528_114153",  # No data
    "z_Intruder_test_160304_152951",  # Test
    "z_USV_test_3612um_1360um_20160307_160307_202140",  # Test
    "z_novel_cage_test_160227_165229",  # Test
]

session_path_list = [
    session
    for subject in data_path.iterdir()
    if subject.is_dir() and subject.name in subject_list
    for session in subject.iterdir()
    if session.is_dir() and session.name not in invalid_session
]


for session_path in session_path_list:
    session_id = session_path.name
    print('----------------')
    print(session_path)
    lfp_file_path = session_path / f"{session_path.name}.lfp"
    raw_file_path = session_path / f"{session_id}.dat"
    xml_file_path = session_path / f"{session_id}.xml"

    nwbfile_path = nwb_output_path / f"{session_id}_stub.nwb"

    source_data = dict(
        NeuroscopeLFP=dict(file_path=str(lfp_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)),
    )
    conversion_options = dict(NeuroscopeLFP=dict(stub_test=stub_test))

    if raw_file_path.is_file():
        source_data.update(
            NeuroscopeRecording=dict(
                file_path=str(raw_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)
            )
        )

    # clu_matches_in_session = len(list(session_path.glob("*.clu*")))
    # res_matches_in_session = len(list(session_path.glob("*.res*")))
    # if clu_matches_in_session > 0 and res_matches_in_session > 0:
    #     source_data.update(
    #         NeuroscopeSorting=dict(
    #             folder_path=str(session_path), keep_mua_units=False, xml_file_path=str(xml_file_path)
    #         )
    #     )

    conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))
    converter = TingleySeptalNWBConverter(source_data)

    metadata = None
    # metadata = converter.get_metadata()
    # metadata["Subject"].update(weight=f"{subject_weight[subject_name]}g")
    converter.run_conversion(
        nwbfile_path=str(nwbfile_path),
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
