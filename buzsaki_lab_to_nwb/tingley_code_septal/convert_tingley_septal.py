from pathlib import Path
import warnings

from scipy.io import loadmat
from nwb_conversion_tools.utils.metadata import load_metadata_from_file
from nwb_conversion_tools.utils.json_schema import dict_deep_update

from buzsaki_lab_to_nwb import TingleySeptalNWBConverter

stub_test = True
conversion_factor = 0.195  # Intan
metadata_path = Path("/home/jovyan/development/buzsaki-lab-to-nwb/buzsaki_lab_to_nwb/tingley_code_septal/metadata.yml")
data_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/")
nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwbfiles")
if stub_test:
    nwb_output_path = Path("/home/jovyan/nwb_test")
else:
    nwb_output_path = Path("/home/jovyan/nwb_test_complete")
nwb_output_path.mkdir(exist_ok=True)

subject_list = ["DT2", "DT5", "DT7", "DT8", "DT9"]

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

# session_path_list = [Path("/shared/catalystneuro/Buzsaki/TingleyD/DT8/20170220_216um_1944um_170220_192456")]

counter = 0
for session_path in session_path_list:
    print("----------------")
    print(session_path)
    counter += 1
    print(f"session {counter} of {len(session_path_list)}")
    session_id = session_path.name
    lfp_file_path = session_path / f"{session_path.name}.lfp"
    raw_file_path = session_path / f"{session_id}.dat"
    xml_file_path = session_path / f"{session_id}.xml"
    spikes_matfile_path = session_path / f"{session_id}.spikes.cellinfo.mat"
    session_info_matfile_path = session_path / f"{session_id}.sessionInfo.mat"
    behavior_matfile_path = session_path / f"{session_id}.behavior.mat"
    if stub_test:
        nwbfile_path = nwb_output_path / f"{session_id}_stub.nwb"
    else:
        nwbfile_path = nwb_output_path / f"{session_id}.nwb"

    print("raw file available", raw_file_path.is_file())
    print("lfp file available", lfp_file_path.is_file())
    print("behavior / position mat file available", behavior_matfile_path.is_file())
    source_data = dict()
    conversion_options = dict()

    source_data = dict(
        NeuroscopeLFP=dict(file_path=str(lfp_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)),
    )
    conversion_options.update(NeuroscopeLFP=dict(stub_test=stub_test))

    if raw_file_path.is_file():
        source_data.update(
            NeuroscopeRecording=dict(
                file_path=str(raw_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)
            )
        )
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test, es_key="ElectricalSeries_raw"))

    clu_matches_in_session = len(list(session_path.glob("*.clu*")))
    res_matches_in_session = len(list(session_path.glob("*.res*")))
    if clu_matches_in_session > 0 and res_matches_in_session > 0:
        print("neuroscope sorted data available", True)
        source_data.update(
            NeuroscopeSorting=dict(
                folder_path=str(session_path), keep_mua_units=False, xml_file_path=str(xml_file_path)
            )
        )
        conversion_options.update(NeuroscopeSorting=dict(stub_test=stub_test))

    if spikes_matfile_path.is_file():
        try:
            print("spikes matlab file available", spikes_matfile_path.is_file())
            loadmat(spikes_matfile_path)
            loadmat(session_info_matfile_path)
            #source_data.update(CellExplorerSorting=dict(spikes_matfile_path=str(spikes_matfile_path)))
            source_data.update(CellExplorerSorting=dict(file_path=str(spikes_matfile_path)))

        except NotImplementedError:
            warnings.warn("The CellExplorer data for this session is of a different version.")

    if behavior_matfile_path.is_file():
        source_data.update(TingleySeptalBehavior=dict(folder_path=str(session_path)))

    converter = TingleySeptalNWBConverter(source_data)

    metadata = converter.get_metadata()
    metadata_from_yaml = load_metadata_from_file(metadata_path)
    metadata = dict_deep_update(metadata, metadata_from_yaml)
    converter.run_conversion(
        nwbfile_path=str(nwbfile_path),
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
