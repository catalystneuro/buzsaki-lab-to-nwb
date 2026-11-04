"""Readers shared by the Valero et al. 2022 interfaces (DANDI:000568)."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
from pymatreader import read_mat

# Fields of session.mat that are large or unused
SESSION_IGNORE_FIELDS = ["behavioralTracking", "timeSeries", "spikeSorting", "brainRegions"]


def read_session(session_path: Path) -> dict:
    """The session struct of `<session>.session.mat`."""
    session_path = Path(session_path)
    file_path = session_path / f"{session_path.name}.session.mat"
    return read_mat(str(file_path), ignore_fields=SESSION_IGNORE_FIELDS)["session"]


def read_cell_metrics_session(session_path: Path) -> Optional[dict]:
    """The copy of session.mat that CellExplorer saved inside cell_metrics.cellinfo.mat, if there is one.

    In some sessions (fCamk5 sess10) the top-level session.mat was later overwritten with template values (species
    Rat, strain Long Evans, epochs with names only), while this copy keeps the animal and the labelled epochs.
    """
    session_path = Path(session_path)
    file_path = session_path / f"{session_path.name}.cell_metrics.cellinfo.mat"
    if not file_path.is_file():
        return None
    general = read_mat(str(file_path), variable_names=["cell_metrics"])["cell_metrics"]["general"]
    return general.get("processinginfo", {}).get("params", {}).get("session")


def session_date(session_id: str) -> date:
    """Recording date from the session id (fCamk1_200827_sess9 is 2020-08-27).

    session.mat gives 2016-03-15 in every session, the date of the lab's session template.
    """
    match = re.match(r"^[A-Za-z0-9]+_(\d{2})(\d{2})(\d{2})_", session_id)
    if match is None:
        raise ValueError(f"Cannot read a date from the session id {session_id}")
    year, month, day = (int(part) for part in match.groups())
    return date(2000 + year, month, day)


def as_list(value) -> list:
    """read_mat returns a struct array of one element as a dict; make it a list."""
    if isinstance(value, dict):
        return [value]
    return list(value)


def electrode_groups(session: dict) -> list:
    """0-indexed channels of each shank (electrode group) in session.mat, in the lab's order."""
    groups = session["extracellular"]["electrodeGroups"]["channels"]
    return [np.atleast_1d(np.asarray(group, dtype=int)) - 1 for group in groups]


def stimulation_notes(session_path: Path) -> list:
    """Names of the empty .txt files the lab left in the session folder (e.g. '4nA pulses.txt', '6nADMSO.txt')."""
    return sorted(path.stem for path in Path(session_path).glob("*.txt"))


def to_json(value) -> str:
    """JSON of a read_mat struct, for descriptions."""

    def convert(item):
        if isinstance(item, dict):
            return {key: convert(val) for key, val in item.items() if not key.startswith("_")}
        if isinstance(item, np.ndarray):
            return item.tolist() if item.size < 50 else f"array of shape {item.shape}"
        if isinstance(item, (np.integer, np.floating)):
            return item.item()
        if isinstance(item, (list, tuple)):
            return [convert(val) for val in item]
        return item

    return json.dumps(convert(value), default=str)


def build_time_intervals(name: str, description: str, start_times, stop_times, columns=()):
    """A TimeIntervals table built from whole columns; `columns` holds (name, description, data) tuples."""
    from hdmf.common import VectorData
    from pynwb.epoch import TimeIntervals

    start_times = np.asarray(start_times, dtype=float)
    vectors = [
        VectorData(name="start_time", description="Start time of epoch, in seconds", data=start_times),
        VectorData(
            name="stop_time", description="Stop time of epoch, in seconds", data=np.asarray(stop_times, dtype=float)
        ),
    ]
    for column_name, column_description, data in columns:
        data = np.asarray(data)
        if data.dtype.kind == "U":
            data = data.tolist()
        vectors.append(VectorData(name=column_name, description=column_description, data=data))
    return TimeIntervals(name=name, description=description, columns=vectors)
