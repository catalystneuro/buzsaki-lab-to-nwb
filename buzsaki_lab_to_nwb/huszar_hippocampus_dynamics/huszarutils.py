"""Readers shared by the interfaces of the Huszar et al. 2022 conversion (DANDI:000552)."""

from pathlib import Path
from typing import Optional

import numpy as np
from pymatreader import read_mat

# The environment the lab names tmaze_familiar in maze_info.mat: the figure-8 maze of the paper's spatial
# alternation task, whose x and y the lab gives in cm (0 to about 92 for the 79 x 79 cm maze)
FAMILIAR_MAZE = "tmaze_familiar"


def as_list(value) -> list:
    """A MATLAB cell array or struct array read by pymatreader as a list (a single element comes back bare)."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, np.ndarray) and value.dtype == object:
        return list(value)
    if isinstance(value, np.ndarray) and value.size == 0:
        return []
    return [value]


def read_session(session_path: Path) -> dict:
    session_path = Path(session_path)
    return read_mat(session_path / f"{session_path.name}.session.mat")["session"]


def read_epochs(session: dict) -> list:
    """The epochs (sub-sessions) of session.mat as dicts with name, startTime and stopTime."""
    return [epoch for epoch in as_list(session.get("epochs")) if isinstance(epoch, dict)]


def read_maze_info(session_path: Path) -> Optional[list]:
    """The environment of each tracked sub-session, in order, from maze_info.mat (novel-environment sessions only)."""
    file_path = Path(session_path) / "maze_info.mat"
    if not file_path.is_file():
        return None
    return [str(name) for name in as_list(read_mat(file_path)["maze_info"])]


def read_tracking(session_path: Path) -> Optional[dict]:
    session_path = Path(session_path)
    file_path = session_path / f"{session_path.name}.Tracking.Behavior.mat"
    if not file_path.is_file():
        return None
    return read_mat(file_path)["tracking"]


def read_behavior(session_path: Path) -> Optional[dict]:
    session_path = Path(session_path)
    file_path = session_path / f"{session_path.name}.Behavior.mat"
    if not file_path.is_file():
        return None
    return read_mat(file_path)["behavior"]


def sub_session_names(session_path: Path) -> list:
    """Folder names of the tracked sub-sessions, in the order the lab numbers them (1, 2, ...).

    Tracking.Behavior.mat lists them; without it, the start times in Behavior.mat events.recordings are matched to
    the epochs of session.mat.
    """
    tracking = read_tracking(session_path)
    if tracking is not None:
        return [str(folder) for folder in as_list(tracking["folders"])]
    behavior = read_behavior(session_path)
    if behavior is None:
        return []
    epochs = read_epochs(read_session(session_path))
    names = []
    for start in np.atleast_1d(behavior["events"]["recordings"]).astype(float):
        matches = [epoch["name"] for epoch in epochs if abs(float(epoch["startTime"]) - start) < 1e-3]
        names.append(str(matches[0]) if matches else "")
    return names


def sub_session_environments(session_path: Path) -> dict:
    """Map the lab's sub-session number (1-indexed) to its maze_info.mat environment, if the session has one."""
    maze_info = read_maze_info(session_path)
    if maze_info is None:
        return {}
    return {index + 1: name for index, name in enumerate(maze_info)}


def birthdate_from_subject_id(subject_id: str) -> str:
    """e13_1m1 -> E13.5: the paper electroporated at E13.5, E14.5, E15.5 and E16.5 and names mice by that day."""
    return f"E{int(subject_id.split('_')[0][1:])}.5"


def sex_from_subject_id(subject_id: str) -> str:
    """e13_1m1 -> M, e15_13f1 -> F."""
    letter = "".join(character for character in subject_id.split("_")[1] if character.isalpha())
    return {"m": "M", "f": "F"}.get(letter, "U")
