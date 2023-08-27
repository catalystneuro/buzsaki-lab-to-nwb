"""Add missing trials tables to a few sessions."""
from pathlib import Path

import numpy as np
from pynwb import NWBHDF5IO
import pymatreader

# Sessions with no trials table written to begin with
# They technically could though, but with a different script
# Conclusion: use the animal timing already in the NWB file instead of the source
FIX_SESSIONS = [
    "Peter-MS10-170307-154746-concat",
    "Peter-MS10-170311-180956-concat",
    "Peter-MS10-170313-122631-concat",
    "Peter-MS10-170319-180352-concat",
    "Peter-MS12-170719-095305-concat",
]
FIX_SESSIONS = [session.replace("-", "_") for session in FIX_SESSIONS]

source_base = Path("F:/Buzsaki/PetersenP")
all_trial_matfiles = list(source_base.rglob("**/trials.mat"))
all_trial_sessions = [path.parent.name.replace("_", "-") for path in all_trial_matfiles]

dandi_base = Path("E:/Buzsaki/PetersenP/000059")
all_dandi_nwbfiles = list(dandi_base.rglob("**/*.nwb"))
all_dandi_sessions = [str(path).split("ses-")[1].split("_")[0] for path in all_dandi_nwbfiles]
all_dandi_nwbfiles_by_session = {
    session_id.replace("-", "_"): path for session_id, path in zip(all_dandi_sessions, all_dandi_nwbfiles)
}

all_trial_starts = dict()
all_trial_ends = dict()
all_trial_time_basis = dict()
fixed_trial_starts = dict()
fixed_trial_ends = dict()
for trial_matfile in all_trial_matfiles:
    session_id = trial_matfile.parent.stem

    if session_id not in FIX_SESSIONS:
        continue

    trial_mat = pymatreader.read_mat(filename=trial_matfile)
    all_trial_starts.update({session_id: trial_mat["trials"]["start"]})
    all_trial_ends.update({session_id: trial_mat["trials"]["end"]})

    nwbfile_path = all_dandi_nwbfiles_by_session[session_id]

    io = NWBHDF5IO(path=nwbfile_path, mode="a")
    nwbfile = io.read()

    all_trial_time_basis.update(
        {session_id: nwbfile.processing["behavior"]["SubjectPosition"]["SpatialSeries"].timestamps[:]}
    )

    fixed_trial_starts.update({session_id: all_trial_time_basis[session_id][all_trial_starts[session_id]]})
    fixed_trial_ends.update({session_id: all_trial_time_basis[session_id][all_trial_ends[session_id]]})

    # Copied and pasted from original conversion script
    trial_info = trial_mat["trials"]
    n_trials = len(all_trial_starts[session_id])
    trial_stat = trial_info["stat"]
    trial_stat_labels = [x for x in trial_info["labels"]]
    cooling_info = trial_info["cooling"]
    cooling_map = dict({0: "Cooling off", 1: "Pre-Cooling", 2: "Cooling on", 3: "Post-Cooling"})
    trial_error = trial_info["error"]
    error_trials = np.array([False] * n_trials)
    error_trials[np.array(trial_error).astype(int) - 1] = True  # -1 from Matlab indexing

    trial_starts = []
    trial_ends = []
    trial_condition = []
    for k in range(n_trials):
        nwbfile.add_trial(start_time=fixed_trial_starts[session_id][k], stop_time=fixed_trial_ends[session_id][k])
        trial_condition.append(trial_stat_labels[int(trial_stat[k]) - 1])

    nwbfile.add_trial_column(
        name="condition",
        description="Whether the maze condition was left or right.",
        data=trial_condition,
    )
    nwbfile.add_trial_column(
        name="error",
        description="Whether the subject made a mistake.",
        data=error_trials,
    )

    if "temperature" in trial_info:  # Some sessions don't have this for some reason
        trial_temperature = trial_info["temperature"]
        nwbfile.add_trial_column(
            name="temperature",
            description="Average brain temperature for the trial.",
            data=trial_temperature,
        )

    if len(cooling_info) == n_trials:  # some sessions had incomplete cooling info
        trial_cooling = [cooling_map[int(cooling_info[k])] for k in range(n_trials)]
        nwbfile.add_trial_column(
            name="cooling state",
            description="The labeled cooling state of the subject during the trial.",
            data=trial_cooling,
        )

    io.write(nwbfile)
    io.close()
