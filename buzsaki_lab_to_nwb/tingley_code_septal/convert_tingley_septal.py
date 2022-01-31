from pathlib import Path
import sys
import warnings

from nwb_conversion_tools.utils.json_schema import load_dict_from_file
from nwb_conversion_tools.utils.json_schema import dict_deep_update

from buzsaki_lab_to_nwb import TingleySeptalNWBConverter
from joblib import Parallel, delayed

n_jobs = 20
stub_test = False
ripple_paper = True
conversion_factor = 0.195  # Intan

data_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/")
home_path = Path("/home/jovyan/")

if ripple_paper:
    metadata_path = Path("./buzsaki_lab_to_nwb/tingley_code_septal/metadata_ripples.yml")
    valid_sessions_path = Path("./buzsaki_lab_to_nwb/tingley_code_septal/valid_sessions_ripples.yml")
else:
    metadata_path = Path("./buzsaki_lab_to_nwb/tingley_code_septal/metadata.yml")
    valid_sessions_path = Path("./buzsaki_lab_to_nwb/tingley_code_septal/valid_sessions.yml")

if stub_test:
    nwb_output_path = home_path / Path("nwb_stub")
else:
    # nwb_output_path = home_path / Path("nwb")
    nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwb")
nwb_output_path.mkdir(exist_ok=True)

valid_session_dic = load_dict_from_file(valid_sessions_path)
valid_sessions_list = []
subject_list = []

for subject, valid_sessions_for_subject in valid_session_dic.items():
    subject_list.append(subject)
    valid_sessions_list += valid_sessions_for_subject

session_path_list = [
    session
    for subject in data_path.iterdir()
    if subject.is_dir() and subject.name in subject_list
    for session in subject.iterdir()
    if session.is_dir() and session.name in valid_sessions_list
]

if stub_test:
    # Number here is to reference in discussion
    nwbfile_list = [
        nwb_output_path / f"{n:03d}_{session.parent.stem}_{session.stem}_stub.nwb"
        for n, session in enumerate(session_path_list)
    ]
else:
    nwbfile_list = [
        nwb_output_path / f"{session.parent.stem}_{session.stem}.nwb" for n, session in enumerate(session_path_list)
    ]


def convert_session(session_path, nwbfile_path):
    print("----------------")
    print(session_path)
    print(nwbfile_path)

    session_id = session_path.name
    lfp_file_path = session_path / f"{session_path.name}.lfp"
    raw_file_path = session_path / f"{session_id}.dat"
    xml_file_path = session_path / f"{session_id}.xml"
    spikes_matfile_path = session_path / f"{session_id}.spikes.cellinfo.mat"
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
