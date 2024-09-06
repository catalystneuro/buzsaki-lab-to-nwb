"""
Issue was detected by Kyu.

Easiest to deploy targetted fix to correct the start_time and stop_time on the trials table reading from the .mat file.

While we're here, might as well paginate and rechunk.
"""
from pathlib import Path

import h5py
import pymatreader

# Sessions with no trials table written to begin with
# They technically could though, but with a different script
# Conclusion: add the trials table during this republication
SKIP_SESSIONS = [
    "Peter-MS10-170307-154746-concat",
    "Peter-MS10-170311-180956-concat",
    "Peter-MS10-170313-122631-concat",
    "Peter-MS10-170319-180352-concat",
    "Peter-MS12-170719-095305-concat",
]

# Sessions that have trials but no processed animal position
# So hard to say how the trial times should be shifted...
# Conclusion: Opted to simply remove these from the dataset
SKIP_SESSIONS += [
    "Peter-MS12-170712-101120-concat",
    "Peter-MS13-171204-102904-concat",
    "Peter-MS13-171205-110831-concat",
    "Peter-MS13-171206-132039-concat",
]

# Index mismatch between trial samples and length of animal series
# (but not take file, which does not match animal series)
# Conclusion: Should remove the trials table altogether from this one
# But it still has other processed data so might be useful
SKIP_SESSIONS += ["Peter_MS21_180712_103200_concat"]

# Prepare for DANDI convention
SKIP_SESSIONS = [session.replace("-", "_") for session in SKIP_SESSIONS]

source_base = Path("F:/Buzsaki/PetersenP")
all_animal_matfiles = list(source_base.rglob("**/animal.mat"))
all_animal_sessions = [path.parent.name.replace("_", "-") for path in all_animal_matfiles]

all_trial_matfiles = list(source_base.rglob("**/trials.mat"))
all_trial_sessions = [path.parent.name.replace("_", "-") for path in all_trial_matfiles]

all_animal_take_files = list(source_base.rglob("**/Take*.csv"))
all_animal_take_sessions = [path.parent.name.replace("_", "-") for path in all_animal_take_files]
all_animal_take_files_by_session = {
    session_id: path for session_id, path in zip(all_animal_take_sessions, all_animal_take_files)
}

dandi_base = Path("E:/Buzsaki/PetersenP/000059")
all_dandi_nwbfiles = list(dandi_base.rglob("**/*.nwb"))
all_dandi_sessions = [str(path).split("ses-")[1].split("_")[0] for path in all_dandi_nwbfiles]

all_trial_starts = dict()
all_trial_ends = dict()
all_trial_time_basis = dict()
current_trial_starts = dict()
current_trial_ends = dict()
fixed_trial_starts = dict()
fixed_trial_ends = dict()
for trial_matfile in all_trial_matfiles:
    session_id = trial_matfile.parent.stem

    if session_id in SKIP_SESSIONS:
        continue

    trial_mat = pymatreader.read_mat(filename=trial_matfile)
    all_trial_starts.update({session_id: trial_mat["trials"]["start"]})
    all_trial_ends.update({session_id: trial_mat["trials"]["end"]})

    animal_matfile = trial_matfile.parent / "animal.mat"
    animal_mat = pymatreader.read_mat(filename=animal_matfile)
    all_trial_time_basis.update({session_id: animal_mat["animal"]["time"]})

    nwbfile_path = next(
        dandi_file for dandi_file in all_dandi_nwbfiles if session_id.replace("_", "-") in str(dandi_file)
    )
    nwbfile = h5py.File(name=nwbfile_path, mode="a")

    current_trial_starts.update({session_id: nwbfile["intervals"]["trials"]["start_time"][:]})
    current_trial_ends.update({session_id: nwbfile["intervals"]["trials"]["stop_time"][:]})

    fixed_trial_starts.update({session_id: all_trial_time_basis[session_id][all_trial_starts[session_id]]})
    fixed_trial_ends.update({session_id: all_trial_time_basis[session_id][all_trial_ends[session_id]]})

    # Deploy fix
    nwbfile["intervals"]["trials"]["start_time"][:] = fixed_trial_starts[session_id]
    nwbfile["intervals"]["trials"]["stop_time"][:] = fixed_trial_ends[session_id]
    nwbfile.close()
