"""Laps on the linear track of a Valero session (DANDI:000568)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.file import NWBFile


class ValeroTrialInterface(BaseDataInterface):
    """Laps from Behavior.mat trials, with the lab's stimulation blocks from its position maps.

    The 2023 conversion read laps only from behavior.cellinfo.mat, which is not in the sessions.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        file_path = self.session_path / f"{self.session_path.name}.Behavior.mat"
        if not file_path.is_file():
            return
        behavior = read_mat(str(file_path), variable_names=["behavior"])["behavior"]
        trials = behavior["trials"]
        intervals = np.atleast_2d(np.asarray(trials["startPoint"], dtype=float))
        if intervals.size == 0:
            return
        visited_arm = np.atleast_1d(np.asarray(trials["visitedArm"], dtype=int))
        recordings = np.atleast_1d(np.asarray(trials["recordings"], dtype=int))

        # Each lap runs from one reward to the next; check that visitedArm 1 is a lap that ends at the left reward
        left = set(np.round(np.atleast_1d(behavior["events"]["lReward"]), 6))
        right = set(np.round(np.atleast_1d(behavior["events"]["rReward"]), 6))
        stops = np.round(intervals[:, 1], 6)
        ends_left = np.array([stop in left for stop in stops])
        ends_right = np.array([stop in right for stop in stops])
        if not (np.all(visited_arm[ends_left] == 1) and np.all(visited_arm[ends_right] == 0)):
            raise ValueError(f"visitedArm of {file_path.name} does not follow the reward at the end of each lap")

        # The lab's position maps split the laps into blocks with and without uLED stimulation
        maps = []
        for key, stimulated in (("noStimulatedMaps", False), ("stimulatedMaps", True)):
            legend = behavior.get(f"{key}Legend")
            if key not in behavior or legend is None:
                continue
            for samples, block in zip(behavior[key], np.atleast_1d(legend["block"])):
                maps.append((np.asarray(samples)[:, 0], stimulated, int(block)))

        def block_of(start, stop):
            counts = [np.sum((times >= start) & (times <= stop)) for times, _, _ in maps]
            if not maps or max(counts) == 0:
                return None, -1
            _, stimulated, block = maps[int(np.argmax(counts))]
            return stimulated, block

        nwbfile.add_trial_column(
            name="visited_arm",
            description="the lab's visitedArm: 1 for a lap that ends at the left end of the track (lReward), 0 for "
            "one that ends at the right end (rReward); the last lap of a run may end without a reward",
        )
        nwbfile.add_trial_column(
            name="recording", description="1-indexed linear track recording of the session (trials.recordings)"
        )
        if maps:
            nwbfile.add_trial_column(
                name="stimulated",
                description="the lap is in a block of runs with uLED stimulation (the lab's stimulatedMaps) rather "
                "than a baseline block (noStimulatedMaps)",
            )
            nwbfile.add_trial_column(
                name="block",
                description="the lab's block number of the lap (maps legend), numbered separately for the "
                "stimulated and the baseline blocks; -1 if in no block",
            )
        for (start, stop), arm, recording in zip(intervals, visited_arm, recordings):
            row = dict(start_time=float(start), stop_time=float(stop), visited_arm=int(arm), recording=int(recording))
            if maps:
                stimulated, block = block_of(start, stop)
                row.update(stimulated=bool(stimulated), block=block)
            nwbfile.add_trial(**row)
