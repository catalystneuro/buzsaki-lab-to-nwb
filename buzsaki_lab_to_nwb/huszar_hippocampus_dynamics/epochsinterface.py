"""Epochs (the recording sub-sessions) of a Huszar session (DANDI:000552)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb.file import NWBFile

from .huszarutils import (
    as_list,
    read_behavior,
    read_epochs,
    read_maze_info,
    read_session,
    read_tracking,
    sub_session_names,
)

NO_ENVIRONMENT = "none"


def tracked_sub_sessions(session_path: Path) -> list:
    """Epochs (name, startTime, stopTime) of the tracked sub-sessions in Tracking.Behavior.mat (folders and
    events.subSessions), for a session whose session.mat lists none."""
    tracking = read_tracking(session_path)
    if tracking is None or not isinstance(tracking.get("events"), dict) or "subSessions" not in tracking["events"]:
        return []
    folders = [str(folder) for folder in as_list(tracking["folders"])]
    intervals = np.atleast_2d(np.asarray(tracking["events"]["subSessions"], dtype=float))
    if len(folders) != len(intervals):
        raise ValueError(f"{len(folders)} tracking folders for {len(intervals)} sub-session intervals")
    return [dict(name=folder, startTime=start, stopTime=stop) for folder, (start, stop) in zip(folders, intervals)]


class HuszarEpochsInterface(BaseDataInterface):
    """One epoch per sub-session of session.mat, named by its recording folder.

    `environment` is the maze_info.mat name of the tracked sub-sessions of the novel-environment sessions, and
    "figure-8 maze" for the sub-session of Behavior.mat in sessions without maze_info.mat; `task` is the
    description of Behavior.mat for the sub-sessions it covers.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        # Leave out entries without a stop time: e13_26m1_211116's session.mat holds only a template entry
        # ("analogin", start 0, no stop). Such a session still has its tracked sub-sessions (folder names and start
        # and stop times) in Tracking.Behavior.mat, which give its epochs; its home-cage periods are then not epochs.
        epochs = [epoch for epoch in read_epochs(read_session(self.session_path)) if "stopTime" in epoch]
        if not epochs:
            epochs = tracked_sub_sessions(self.session_path)
        if not epochs:
            return
        maze_info = read_maze_info(self.session_path)
        folders = sub_session_names(self.session_path)
        behavior = read_behavior(self.session_path)

        environments, tasks = {}, {}
        for index, folder in enumerate(folders):
            if maze_info is not None and index < len(maze_info):
                environments[folder] = maze_info[index]
        if behavior is not None:
            descriptions = [str(description) for description in as_list(behavior["description"])]
            numbers = np.unique(np.atleast_1d(behavior["masks"]["recording"]).astype(int))
            for number, description in zip(numbers, descriptions):
                if number <= len(folders):
                    tasks[folders[number - 1]] = description
                    if maze_info is None:
                        environments[folders[number - 1]] = "figure-8 maze"

        nwbfile.add_epoch_column(name="epoch_name", description="name of the sub-session: its recording folder")
        nwbfile.add_epoch_column(
            name="environment",
            description=(
                "environment of the sub-session: the maze_info.mat name in the novel-environment sessions, "
                f"'figure-8 maze' for the maze sub-session of the other sessions, '{NO_ENVIRONMENT}' for sub-sessions "
                "without tracking (the paper describes home-cage periods before and after the maze)"
            ),
        )
        nwbfile.add_epoch_column(
            name="task",
            description=f"task of the sub-session (Behavior.mat description); '{NO_ENVIRONMENT}' if not in Behavior.mat",
        )
        for epoch in sorted(epochs, key=lambda epoch: float(epoch["startTime"])):
            name = str(epoch["name"])
            nwbfile.add_epoch(
                start_time=float(epoch["startTime"]),
                stop_time=float(epoch["stopTime"]),
                epoch_name=name,
                environment=environments.get(name, NO_ENVIRONMENT),
                task=tasks.get(name, NO_ENVIRONMENT),
            )
