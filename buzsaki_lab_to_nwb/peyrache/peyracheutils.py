"""Helpers for reading the Peyrache et al. 2015 (DANDI:000056, CRCNS th-1) source files."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree
from scipy.io import loadmat

SAMPLING_RATE = 20_000.0
LFP_RATE = 1250.0
POSITION_RATE = 1250 / 32  # 39.0625 Hz, the .whl/.pos/.ang rate (the .xml gives the same)
TS_PER_SECOND = 1e4  # TSToolbox intervalSets in the Analysis files count time in 0.1 ms steps

# Region names of GeneralInfo.mat's shankStructure, with the electrode location written for them
REGION_LOCATIONS = {
    "thalamus": "Anterodorsal nucleus",
    "postsub": "Postsubiculum",
    "hippocampus": "Field CA1",
    "pfc": "Prelimbic area",
    "rtn": "Reticular nucleus of the thalamus",
}
REGION_DESCRIPTIONS = {
    "thalamus": (
        "the lab labels this group 'thalamus' (GeneralInfo.mat shankStructure). The thalamic probe was aimed at the "
        "anterodorsal (AD) nucleus; the CRCNS th-1 description says the thalamic electrodes are in several anterior "
        "thalamic nuclei, mainly AD, confirmed by histology"
    ),
    "postsub": (
        "the lab labels this group 'postsub' (GeneralInfo.mat shankStructure): post-subiculum, confirmed by histology "
        "according to the CRCNS th-1 description"
    ),
    "hippocampus": (
        "the lab labels this group 'hippocampus' (GeneralInfo.mat shankStructure): tungsten wires aimed at the CA1 "
        "pyramidal layer, used for the hippocampal LFP (sleep scoring and ripples)"
    ),
    "pfc": (
        "the lab labels this group 'pfc' (GeneralInfo.mat shankStructure): tetrodes in the medial prefrontal cortex, "
        "in the prelimbic area according to the session's .xml description"
    ),
    "rtn": (
        "the lab labels this group 'rtn' (GeneralInfo.mat shankStructure), presumably the thalamic reticular nucleus; "
        "the session's .xml description does not mention this group"
    ),
    "optic": (
        "the lab labels this group 'optic' (GeneralInfo.mat shankStructure); it is not described, and is probably "
        "not a recording electrode (light stimulation)"
    ),
}

# Behavior epochs of BehavEpochs.mat (intervalSet name: tag and description)
BEHAVIOR_EPOCHS = {
    "sleepPreEp": ("sleep_pre", "rest and sleep in the home cage before the open-field exploration"),
    "wakeEp": ("open_field", "exploration of the open field (53 x 46 cm), the epoch of the paper's wake analyses"),
    "sleepPostEp": ("sleep_post", "rest and sleep in the home cage after the open-field exploration"),
    "radEp": (
        "second_environment",
        "exploration of a second, larger environment (the lab's radEp; the files do not describe it further)",
    ),
    "radRestEp": ("rest_after_second_environment", "rest after the second environment (the lab's radRestEp)"),
    "wakeOptoEp": ("wake_opto", "wake with optogenetic stimulation (the lab's wakeOptoEp)"),
    "restOptoEp": ("rest_opto", "rest with optogenetic stimulation (the lab's restOptoEp)"),
}


def split_session_id(session_id: str) -> tuple:
    """Return (mouse, date) for names like Mouse12-120806."""
    match = re.fullmatch(r"(Mouse\d+)-(\d{6})", session_id)
    if match is None:
        raise ValueError(f"Unexpected session name {session_id}")
    mouse, date = match.groups()
    return mouse, pd.Timestamp(f"20{date[:2]}-{date[2:4]}-{date[4:]}").to_pydatetime()


def read_session_xml(xml_file_path: Path) -> dict:
    """Acquisition settings, anatomical groups and spike groups of a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    anatomical_groups = [
        [int(channel.text) for channel in group.findall("channel")]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    spike_groups = [
        [int(channel.text) for channel in group.find("channels")]
        for group in root.find("spikeDetection").find("channelGroups").findall("group")
    ]
    # The spike groups (numbering of the .clu/.res files and of the lab's `shank`) are a subset of the anatomical
    # groups (numbering of the lab's shankStructure and of the .xml description); the two differ in some sessions
    spike_to_anatomical = []
    for channels in spike_groups:
        matches = [index + 1 for index, group in enumerate(anatomical_groups) if set(channels) <= set(group)]
        if len(matches) != 1:
            raise ValueError(f"spike group with channels {channels} is not in exactly one anatomical group")
        spike_to_anatomical.append(matches[0])
    description = root.find("generalInfo").findtext("description") or ""
    return dict(
        n_channels=int(acquisition.find("nChannels").text),
        sampling_rate=float(acquisition.find("samplingRate").text),
        n_bits=int(acquisition.find("nBits").text),
        voltage_range=float(acquisition.find("voltageRange").text),
        amplification=float(acquisition.find("amplification").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        anatomical_groups=anatomical_groups,
        spike_groups=spike_groups,
        spike_to_anatomical=spike_to_anatomical,
        description=description.strip(),
    )


def load_mat(file_path: Path, **kwargs) -> dict:
    return loadmat(str(file_path), squeeze_me=True, struct_as_record=False, **kwargs)


def read_shank_structure(general_info: dict) -> dict:
    """Anatomical group number -> region name, from GeneralInfo.mat's shankStructure (a containers.Map)."""
    structure = general_info["shankStructure"]
    regions = {}
    for key, value in zip(np.atleast_1d(structure.keys), np.atleast_1d(structure.values)):
        for group in np.atleast_1d(value).astype(int).tolist():
            regions[group] = str(key)
    return regions


def interval_set(value) -> np.ndarray:
    """(n, 2) start and stop in seconds of a TSToolbox intervalSet."""
    start = np.atleast_1d(np.asarray(value.start, dtype=float)).ravel()
    stop = np.atleast_1d(np.asarray(value.stop, dtype=float)).ravel()
    return np.column_stack([start, stop]) / TS_PER_SECOND


def tsd_times(value) -> np.ndarray:
    """Times in seconds of a TSToolbox ts/tsd object."""
    return np.atleast_1d(np.asarray(value.tsd.t, dtype=float)).ravel() / TS_PER_SECOND


def read_dat_segments(session_path: Path) -> list:
    """(file name, start, stop) in seconds of the session's sub-recordings, from DatSegments.txt and the .srs file.

    DatSegments.txt gives the length of each sub-recording (-NN.dat file) in LFP samples (1250 Hz); the clustered
    data concatenate them in order, from time 0.
    """
    session_id = session_path.name
    lengths = np.loadtxt(session_path / "DatSegments.txt", ndmin=1)
    srs_file_path = session_path / f"{session_id}.srs"
    names = srs_file_path.read_text().split() if srs_file_path.is_file() else []
    if len(names) != len(lengths):
        names = [f"{session_id}-{index + 1:02d}" for index in range(len(lengths))]
    bounds = np.concatenate([[0], np.cumsum(lengths)]) / LFP_RATE
    return [(name, float(bounds[index]), float(bounds[index + 1])) for index, name in enumerate(names)]


def read_columns(file_path: Path, n_columns: int) -> tuple:
    """Numeric columns of a whitespace-separated text file, tolerating malformed lines.

    Returns the (n_lines, n_columns) array and the 1-indexed numbers of the lines that did not have n_columns numbers,
    which are set to NaN (Mouse17-130201's .pos has two such lines, written by interleaved writes).
    """
    lines = file_path.read_text().splitlines()
    data = np.full((len(lines), n_columns), np.nan)
    malformed = []
    for index, line in enumerate(lines):
        fields = line.split()
        if len(fields) != n_columns:
            malformed.append(index + 1)
            continue
        try:
            data[index] = [float(field) for field in fields]
        except ValueError:
            malformed.append(index + 1)
    return data, malformed


def read_session_info(xls_file_path: Path) -> pd.DataFrame:
    """The CRCNS th-1 session table (crcns_th-1_session_info.xls), one row per session."""
    table = pd.read_excel(xls_file_path, header=0)
    table.columns = [
        "animal",
        "session",
        "thalamus",
        "thalamus_groups",
        "thalamus_depth",
        "Postsubiculum",
        "postsubiculum_groups",
        "postsubiculum_depth",
        "hippocampus",
        "hippocampus_groups",
    ][: len(table.columns)]
    table["animal"] = table["animal"].ffill()
    return table.dropna(subset=["session"]).set_index("session")


def read_events(evt_file_path: Path) -> pd.DataFrame:
    """Times (s) and labels of a Neuroscope .evt file (times in ms)."""
    events = pd.read_csv(evt_file_path, sep="\t", header=None, names=["ms", "label"], dtype={"label": str})
    events["label"] = events["label"].fillna("").str.strip()
    events["time"] = events["ms"].to_numpy(dtype=float) / 1000
    return events
