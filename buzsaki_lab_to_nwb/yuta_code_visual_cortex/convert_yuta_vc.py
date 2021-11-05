"""Authors: Heberto Mayorquin and Cody Baker."""
import sys
from pathlib import Path

from joblib import Parallel, delayed
from nwb_conversion_tools.utils.metadata import load_metadata_from_file
from nwb_conversion_tools.utils.json_schema import dict_deep_update, FilePathType, FolderPathType

from buzsaki_lab_to_nwb import YutaVCNWBConverter

n_jobs = 10

# data_path = Path("/home/heberto/globus_data")
data_path = Path("/shared/catalystneuro/Buzsaki/SenzaiY")
nwb_output_path = Path("/home/jovyan/BuzsakiNWB/SenzaiY")
metadata_path = Path("metadata.yml")


stub_test = True
conversion_factor = 0.195  # Intan

session_list = [
    session
    for subject in data_path.iterdir()
    if subject.is_dir() and "YMV" in subject.name
    for session in subject.iterdir()
]
session_list = [session for session in session_list if session.is_dir()]
nwbfile_list = [nwb_output_path / f"{session.stem}.nwb" for session in session_list]

subject_genotypes = dict(YMV04="CaMKII-Cre::Ai32", YMV07="CaMKII-Cre::Ai35")
subject_genotypes.update({f"YMV{subject_num}": "Ai35" for subject_num in ["01", "02", "03"]})
subject_genotypes.update(
    {f"YMV{subject_num}": "PV-Cre::Ai32" for subject_num in ["05", "09", "10", "11"] + [str(x) for x in range(13, 20)]}
)
subject_genotypes.update({f"YMV{subject_num}": "VGAT-Cre::Ai32" for subject_num in ["06", "08", "12"]})


def convert_session(session_path: FolderPathType, nwbfile_path: FilePathType):
    """Wrap converter for Parallel use."""
    print(f"Processsing {session_path}...")
    session_name = session_path.stem
    subject_name = session_path.parent.name
    dat_file_path = session_path / f"{session_name}.dat"
    eeg_file_path = session_path / f"{session_name}.eeg"

    source_data = dict(
        NeuroscopeRecording=dict(file_path=str(dat_file_path), gain=conversion_factor),
        NeuroscopeLFP=dict(file_path=str(eeg_file_path), gain=conversion_factor),
        YutaVCBehavior=dict(folder_path=str(session_path)),
        PhySorting=dict(folder_path=str(session_path), exclude_cluster_groups=["noise", "mua"]),
    )
    converter = YutaVCNWBConverter(source_data=source_data)
    conversion_options = dict(
        NeuroscopeRecording=dict(stub_test=stub_test),
        NeuroscopeLFP=dict(stub_test=stub_test),
        PhySorting=dict(stub_test=stub_test),
    )
    metadata = converter.get_metadata()
    metadata["Subject"].update(genotype=subject_genotypes[subject_name])
    metadata_from_yaml = load_metadata_from_file(metadata_path)
    metadata = dict_deep_update(metadata, metadata_from_yaml)
    converter.run_conversion(
        nwbfile_path=str(nwbfile_path), conversion_options=conversion_options, metadata=metadata, overwrite=True
    )
    sys.stdout.flush()  # Needed for verbosity in Parallel


Parallel(n_jobs=n_jobs)(
    delayed(convert_session)(session_path=session_path, nwbfile_path=nwbfile_path)
    for session_path, nwbfile_path in zip(session_list, nwbfile_list)
)
