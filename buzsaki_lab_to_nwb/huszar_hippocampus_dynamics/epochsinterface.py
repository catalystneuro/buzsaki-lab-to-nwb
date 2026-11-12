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


def behavior_sub_sessions(session_path: Path) -> list:
    """Epochs of the maze sub-sessions in Behavior.mat, for a session without Tracking.Behavior.mat: each starts at
    its events.recordings time and ends at its last tracked frame (the source gives no stop time), with its
    environment and task."""
    behavior = read_behavior(session_path)
    if behavior is None:
        return []
    starts = np.atleast_1d(np.asarray(behavior["events"]["recordings"], dtype=float))
    timestamps = np.atleast_1d(np.asarray(behavior["timestamps"], dtype=float))
    masks = np.atleast_1d(behavior["masks"]["recording"]).astype(int)
    descriptions = [str(description) for description in as_list(behavior["description"])]
    maze_info = read_maze_info(session_path)
    epochs = []
    for number in np.unique(masks):
        if number < 1 or number > len(starts):
            continue
        epochs.append(
            dict(
                name=f"maze sub-session {number} (Behavior.mat)",
                startTime=starts[number - 1],
                stopTime=float(timestamps[masks == number].max()),
                environment=maze_info[number - 1] if maze_info and number <= len(maze_info) else "figure-8 maze",
                task=descriptions[number - 1] if number <= len(descriptions) else NO_ENVIRONMENT,
            )
        )
    return epochs


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
        # Add the tracked sub-sessions that session.mat's epochs do not cover: in some sessions they end before the
        # maze (e14_2m3_201017: one epoch, 0 to 6,768 s; maze tracking 6,793 to 8,943 s)
        names = {str(epoch["name"]) for epoch in epochs}
        for tracked in tracked_sub_sessions(self.session_path) or behavior_sub_sessions(self.session_path):
            start, stop = float(tracked["startTime"]), float(tracked["stopTime"])
            covered = sum(
                max(0.0, min(stop, float(epoch["stopTime"])) - max(start, float(epoch["startTime"]))) for epoch in epochs
            )
            if tracked["name"] not in names and covered < 0.5 * (stop - start):
                epochs.append(tracked)
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

        nwbfile.add_epoch_column(
            name="epoch_name",
            description=(
                "name of the sub-session: its recording folder, or 'maze sub-session N (Behavior.mat)' for a maze "
                "sub-session that session.mat does not list, which runs from its Behavior.mat start to its last "
                "tracked frame"
            ),
        )
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
                environment=epoch.get("environment", environments.get(name, NO_ENVIRONMENT)),
                task=epoch.get("task", tasks.get(name, NO_ENVIRONMENT)),
            )
