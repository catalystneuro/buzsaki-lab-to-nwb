"""Helpers for reading the Petersen and Buzsaki 2020 (DANDI:000059) source files."""

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pymatreader
from lxml import etree

# Cooling codes of the lab's trials files (trials.cooling), named by animal.state_labels (Pre, Cooling, Post)
COOLING_STATE_LABELS = {1: "Pre", 2: "Cooling", 3: "Post"}
TRANSITION_LABEL = "transition (excluded)"
UNLABELLED = "not labelled"


def read_mat(file_path: Path) -> dict:
    """A MATLAB file (v5 or v7.3) as nested dicts and numpy arrays."""
    return pymatreader.read_mat(str(file_path))


def split_session_id(session_id: str) -> tuple:
    """Subject and start time of names like Peter_MS21_180719_155941_concat or Peter_MS21_180621_141817."""
    match = re.fullmatch(r"Peter_(MS\d+)_(\d{6}_\d{6})(_concat)?", session_id)
    if match is None:
        raise ValueError(f"Unexpected session name {session_id}")
    start = datetime.strptime(match.group(2), "%y%m%d_%H%M%S").replace(tzinfo=ZoneInfo("America/New_York"))
    return match.group(1), start


def read_session_xml(xml_file_path: Path) -> dict:
    """Acquisition settings and electrode (spike) groups, as 0-based channels, from a Neuroscope .xml file.

    Where the spike groups are missing or leave channels out, the anatomical groups are used.
    """
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    n_channels = int(acquisition.find("nChannels").text)
    spike_groups = root.find("spikeDetection/channelGroups")
    groups = []
    if spike_groups is not None:
        groups = [[int(channel.text) for channel in group.find("channels")] for group in spike_groups.findall("group")]
    if sorted(sum(groups, [])) != list(range(n_channels)):
        # No spike groups, or spike groups that leave channels out (Peter_MS10_170314_163038: 47 of 64): the anatomical
        # groups, which hold every channel
        groups = [
            [int(channel.text) for channel in group.findall("channel")]
            for group in root.find("anatomicalDescription/channelGroups").findall("group")
        ]
    return dict(
        n_channels=n_channels,
        sampling_rate=float(acquisition.find("samplingRate").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        groups=groups,
    )


def as_list(value) -> list:
    """A MATLAB scalar, vector, empty array or cell array as a list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return np.atleast_1d(np.asarray(value)).tolist()


def read_phy_labels(folder_path: Path) -> pd.Series:
    """Phy cluster labels: cluster_info.tsv (`group`), else cluster_group.tsv, else the older cluster_groups.csv."""
    for name in ("cluster_info.tsv", "cluster_group.tsv", "cluster_groups.csv"):
        file_path = folder_path / name
        if file_path.is_file():
            table = pd.read_csv(file_path, sep="\t")
            column = "group" if "group" in table.columns else "KSLabel"
            return table.set_index("cluster_id")[column].fillna("unsorted").astype(str), name
    return pd.Series(dtype=str), None


def trial_states(state: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """The cooling state (1-3) of each trial in the lab's per-sample state vector; 0 if it has none, -1 if mixed.

    `starts` and `ends` are the lab's 1-based sample indices.
    """
    codes = []
    for start, end in zip(starts, ends):
        segment = state[int(start) - 1 : int(end)]
        values = np.unique(segment[~np.isnan(segment)])
        codes.append(int(values[0]) if len(values) == 1 else (0 if len(values) == 0 else -1))
    return np.array(codes)


def intervals(array) -> list:
    """(start, stop) pairs of the lab's interval arrays: a pair, or a 2 x n array with one interval per column."""
    array = np.asarray(array, dtype=float)
    if array.size == 0:
        return []
    if array.ndim == 1:
        return [tuple(array)]
    if array.shape[0] != 2:
        array = array.T
    return [tuple(column) for column in array.T]


def read_session_mat(session_path: Path, session_id: str) -> dict:
    """The lab's CellExplorer session struct: <session>.session.mat, or the older session.mat of the folder.

    Where the first lacks the gain (extracellular.leastSignificantBit) or the probe list (extracellular.electrodes)
    and the older file has them, they are taken from the older file.
    """
    named, plain = session_path / f"{session_id}.session.mat", session_path / "session.mat"
    if not named.is_file():
        return read_mat(plain)["session"]
    session = read_mat(named)["session"]
    if plain.is_file():
        older = read_mat(plain)["session"].get("extracellular", {})
        extracellular = session.setdefault("extracellular", {})
        for key in ("leastSignificantBit", "electrodes"):
            if key not in extracellular and key in older:
                extracellular[key] = older[key]
    return session


def as_dict(value) -> dict:
    """A MATLAB struct as a dict; an empty array (an empty struct field) as {}."""
    return value if isinstance(value, dict) else {}
