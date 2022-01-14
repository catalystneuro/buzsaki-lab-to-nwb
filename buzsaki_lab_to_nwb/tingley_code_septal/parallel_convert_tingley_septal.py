from pathlib import Path
import sys
import warnings

from scipy.io import loadmat
from nwb_conversion_tools.utils.json_schema import load_dict_from_file
from nwb_conversion_tools.utils.json_schema import dict_deep_update

from buzsaki_lab_to_nwb import TingleySeptalNWBConverter
from joblib import Parallel, delayed

n_jobs = 20
stub_test = True
conversion_factor = 0.195  # Intan
metadata_path = Path("/home/jovyan/development/buzsaki-lab-to-nwb/buzsaki_lab_to_nwb/tingley_code_septal/metadata.yml")

data_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/")

if stub_test:
    nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwb_stub")
else:
    nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwb")
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

if stub_test:
    # Number here is to reference in discussion
    nwbfile_list = [nwb_output_path / f"{n:03d}_{session.stem}_stub.nwb" for n, session in enumerate(session_path_list)]
else:
    nwbfile_list = [nwb_output_path / f"{session.stem}.nwb" for n, session in enumerate(session_path_list)]


def convert_session(session_path, nwbfile_path):
    print("----------------")
    print(session_path)
    print(nwbfile_path)
    
    session_id = session_path.name
    lfp_file_path = session_path / f"{session_path.name}.lfp"
    raw_file_path = session_path / f"{session_id}.dat"
    xml_file_path = session_path / f"{session_id}.xml"
    spikes_matfile_path = session_path / f"{session_id}.spikes.cellinfo.mat"
    session_info_matfile_path = session_path / f"{session_id}.sessionInfo.mat"
    behavior_matfile_path = session_path / f"{session_id}.behavior.mat"


    print("raw file available", raw_file_path.is_file())
    print("lfp file available", lfp_file_path.is_file())
    print("behavior / position mat file available", behavior_matfile_path.is_file())
    source_data = dict()
    conversion_options = dict()

    source_data = dict(
        NeuroscopeLFP=dict(file_path=str(lfp_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)),
    )
    conversion_options.update(NeuroscopeLFP=dict(stub_test=stub_test))
    # conversion_options.update(NeuroscopeLFP=dict(stub_test=stub_test, es_key="lfp"))

    if raw_file_path.is_file():
        source_data.update(
            NeuroscopeRecording=dict(
                file_path=str(raw_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)
            )
        )
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test, es_key="ElectricalSeries_raw"))

    clu_matches_in_session = len(list(session_path.glob("*.clu*")))
    res_matches_in_session = len(list(session_path.glob("*.res*")))

    if spikes_matfile_path.is_file():
        print("cell explorer spiking data is used")
        source_data.update(CellExplorerSorting=dict(file_path=str(spikes_matfile_path)))
    else:
        if clu_matches_in_session > 0 and res_matches_in_session > 0:
            print("neuroscope spiking data is used")
            source_data.update(
                NeuroscopeSorting=dict(
                    folder_path=str(session_path), keep_mua_units=False, xml_file_path=str(xml_file_path)
                )
            )
            conversion_options.update(NeuroscopeSorting=dict(stub_test=stub_test))
        else:
            print("not spiking data available")

    if behavior_matfile_path.is_file():
        source_data.update(TingleySeptalBehavior=dict(folder_path=str(session_path)))

    converter = TingleySeptalNWBConverter(source_data)

    metadata = None
    metadata = converter.get_metadata()
    metadata_from_yaml = load_dict_from_file(metadata_path)
    metadata = dict_deep_update(metadata, metadata_from_yaml)

    converter.run_conversion(
        nwbfile_path=str(nwbfile_path),
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
    print("Done with conversion")
    sys.stdout.flush()  # Needed for verbosity in Parallel


Parallel(n_jobs=n_jobs)(
    delayed(convert_session)(session_path=session_path, nwbfile_path=nwbfile_path)
    for session_path, nwbfile_path in zip(session_path_list, nwbfile_list)
)
