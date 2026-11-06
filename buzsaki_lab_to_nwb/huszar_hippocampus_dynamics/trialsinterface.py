"""Trials of the spatial alternation task of a Huszar session (DANDI:000552)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb.file import NWBFile

from .huszarutils import FAMILIAR_MAZE, read_behavior, sub_session_environments

# Behavior.mat codes the arms 0 and 1. Every rReward event falls in a trial with visitedArm 1 and every lReward event
# in a trial with visitedArm 0 (checked in the converted sessions), so 1 is the right arm and 0 the left arm.
ARMS = {0: "left", 1: "right"}


def to_arm(values) -> list:
    return [ARMS[int(value)] if value == value else "none" for value in np.asarray(values, dtype=float)]


class HuszarTrialsInterface(BaseDataInterface):
    """Trials of Behavior.mat, in the lab's order (by start time)."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        trials = read_behavior(self.session_path)["trials"]
        # One array of [start, stop] rows per maze sub-session
        trial_ints = trials["trial_ints"]
        if isinstance(trial_ints, np.ndarray) and trial_ints.dtype != object:
            trial_ints = [trial_ints]
        trial_ints = [np.atleast_2d(np.asarray(ints, dtype=float)) for ints in trial_ints]
        intervals = np.concatenate(trial_ints)
        recordings = np.atleast_1d(trials["recordings"]).astype(int)
        if len(recordings) != len(intervals):
            raise ValueError(f"{len(intervals)} trial intervals for {len(recordings)} trial recordings")

        environments = sub_session_environments(self.session_path)
        is_familiar = [environments.get(int(recording), FAMILIAR_MAZE) == FAMILIAR_MAZE for recording in recordings]
        # The trials of each maze sub-session come in one block of trial_ints
        blocks = np.repeat(np.arange(len(trial_ints)), [len(ints) for ints in trial_ints])
        if not all(len(set(recordings[blocks == block])) == 1 for block in np.unique(blocks)):
            raise ValueError("The trials of a trial_ints block span several sub-sessions")

        for start_time, stop_time in intervals:
            nwbfile.add_trial(start_time=float(start_time), stop_time=float(stop_time))

        nwbfile.add_trial_column(
            name="visited_matched_expected",
            description="1 if the visited arm was the expected arm, 0 if not, NaN if undefined (Behavior.mat choice)",
            data=np.asarray(trials["choice"], dtype=float),
        )
        nwbfile.add_trial_column(
            name="visited_arm",
            description="arm the mouse visited (Behavior.mat visitedArm: 0 left, 1 right)",
            data=to_arm(trials["visitedArm"]),
        )
        nwbfile.add_trial_column(
            name="expected_arm",
            description="arm the alternation rule called for (Behavior.mat expectedArm: 0 left, 1 right); none if undefined",
            data=to_arm(trials["expectedArm"]),
        )
        nwbfile.add_trial_column(
            name="recordings",
            description="the lab's number of the sub-session of the trial (Behavior.mat trials.recordings)",
            data=recordings,
        )
        nwbfile.add_trial_column(
            name="is_familiar_maze",
            description=(
                "the trial is in the familiar figure-8 maze (tmaze_familiar of maze_info.mat, or every trial of a "
                "session without maze_info.mat)"
            ),
            data=is_familiar,
        )
