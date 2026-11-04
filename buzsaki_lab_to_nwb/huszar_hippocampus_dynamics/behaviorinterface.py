"""Position, maze events and sleep states of a Huszar session (DANDI:000552)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.behavior import Position, SpatialSeries
from pynwb.epoch import TimeIntervals
from pynwb.event import EventsTable
from pynwb.file import NWBFile

from .huszarutils import FAMILIAR_MAZE, read_behavior, read_maze_info, read_tracking, sub_session_names

BEHAVIOR_MODULE_DESCRIPTION = "behavior: position in the mazes, maze events and sleep states"


def behavior_module(nwbfile: NWBFile):
    return get_module(nwbfile=nwbfile, name="behavior", description=BEHAVIOR_MODULE_DESCRIPTION)


class HuszarPositionInterface(BaseDataInterface):
    """Position of each tracked sub-session.

    Behavior.mat holds x, y and the linearized position of the sub-sessions with a maze task (it is the file the
    trials come from). Tracking.Behavior.mat, in the novel-environment sessions, also holds the sub-sessions that
    Behavior.mat leaves out (the open fields). The lab's x and y are in cm in the familiar figure-8 maze; in the
    other environments some sub-sessions are between 0 and 1 and the open fields between 0 and about 35, with no
    scale given in the source, so they are written in the lab's units, with unit "n.a.".
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        behavior = read_behavior(self.session_path)
        tracking = read_tracking(self.session_path)
        maze_info = read_maze_info(self.session_path)
        folders = sub_session_names(self.session_path)

        # sub-session number -> (timestamps, x, y, lin or None, source)
        segments = {}
        if behavior is not None:
            recording = np.atleast_1d(behavior["masks"]["recording"]).astype(int)
            for number in np.unique(recording):
                mask = recording == number
                segments[int(number)] = (
                    np.asarray(behavior["timestamps"])[mask],
                    np.asarray(behavior["position"]["x"])[mask],
                    np.asarray(behavior["position"]["y"])[mask],
                    np.asarray(behavior["position"]["lin"])[mask],
                    "Behavior.mat",
                )
        if tracking is not None:
            mask_all = np.atleast_1d(tracking["events"]["subSessionsMask"]).astype(int)
            for number in np.unique(mask_all):
                if int(number) in segments:
                    continue
                mask = mask_all == number
                segments[int(number)] = (
                    np.asarray(tracking["timestamps"])[mask],
                    np.asarray(tracking["position"]["x"])[mask],
                    np.asarray(tracking["position"]["y"])[mask],
                    None,
                    "Tracking.Behavior.mat",
                )
        if not segments:
            return

        module = behavior_module(nwbfile)
        position = Position(name="SubjectPosition")
        linearized = Position(name="LinearizedPosition")
        for number, (timestamps, x, y, lin, source) in sorted(segments.items()):
            environment = maze_info[number - 1] if maze_info and number <= len(maze_info) else None
            folder = folders[number - 1] if number <= len(folders) else ""
            familiar = environment in (None, FAMILIAR_MAZE)
            where = f"sub-session {number}" + (f" ({folder})" if folder else "")
            where += f", environment {environment} (maze_info.mat)" if environment else ", the figure-8 maze"
            data = np.column_stack((x, y))
            if familiar:
                unit, scale = "centimeters", "in cm"
            else:
                unit = "n.a."
                scale = (
                    f"in the lab's units: x {np.nanmin(x):.2f} to {np.nanmax(x):.2f}, y {np.nanmin(y):.2f} to "
                    f"{np.nanmax(y):.2f}, with no scale given in the source"
                )
            name = f"SpatialSeries{number}" + (f"_{environment}" if environment else "")
            position.add_spatial_series(
                SpatialSeries(
                    name=name,
                    description=f"(x, y) of the head-mounted LEDs in {where}, from the lab's {source}, {scale}",
                    data=data,
                    reference_frame="the lab's camera coordinates",
                    unit=unit,
                    timestamps=timestamps,
                )
            )
            if lin is not None:
                linearized.add_spatial_series(
                    SpatialSeries(
                        name=f"LinearizedSpatialSeries{number}" + (f"_{environment}" if environment else ""),
                        description=f"linearized position along the maze in {where}, from the lab's Behavior.mat",
                        data=lin,
                        reference_frame="0 at the start of the lab's linearized maze path",
                        unit="centimeters",
                        timestamps=timestamps,
                    )
                )
        module.add(position)
        if linearized.spatial_series:
            module.add(linearized)


class HuszarBehavior8MazeRewardsInterface(BaseDataInterface):
    """The rReward and lReward events of Behavior.mat."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        behavior = read_behavior(self.session_path)
        events = behavior["events"]
        right = np.atleast_1d(events["rReward"]).astype(float)
        left = np.atleast_1d(events["lReward"]).astype(float)
        timestamps = np.concatenate([right, left])
        arms = np.array(["right"] * len(right) + ["left"] * len(left))
        order = np.argsort(timestamps, kind="stable")

        table = EventsTable(
            name="RewardEvents",
            description=(
                "times of the lab's rReward (right) and lReward (left) events of Behavior.mat. Each falls in a trial "
                "whose visited arm is that side, including trials the lab scored as errors, so whether they mark "
                "water delivery or the arrival at the reward corner is not stated in the source"
            ),
            source_description="Behavior.mat events.rReward and events.lReward",
        )
        table.add_column(name="arm", description="side of the reward corner: right (rReward) or left (lReward)")
        for index in order:
            table.add_event(timestamp=float(timestamps[index]), arm=str(arms[index]))
        behavior_module(nwbfile).add(table)


class HuzsarBehaviorSleepInterface(BaseDataInterface):
    """Brain states scored by the lab (SleepState.states.mat)."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"
        intervals = read_mat(file_path, variable_names=["SleepState"])["SleepState"]["ints"]

        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        table = TimeIntervals(
            name="SleepStates",
            description="brain state of the mouse, scored by the lab (SleepState.states.mat ints)",
        )
        table.add_column(name="label", description="brain state")
        rows = []
        for state, label in state_label_names.items():
            values = np.asarray(intervals.get(state, []), dtype=float)
            if values.size == 0:
                continue
            for start_time, stop_time in values.reshape(-1, 2):
                rows.append(dict(start_time=float(start_time), stop_time=float(stop_time), label=label))
        for row in sorted(rows, key=lambda row: row["start_time"]):
            table.add_row(**row)
        behavior_module(nwbfile).add(table)
