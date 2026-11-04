"""Helpers for reading the Grosmark and Buzsaki 2016 (DANDI:000044, CRCNS hc-11) source files."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from lxml import etree
from scipy.io import loadmat

# The Amplipex KJE-1001 of the .meta files: +-5 V over 16 bits at x400 gain, 0.3815 uV per step. The .xml files give
# 20 V and x1000 (0.305 uV per step), which look like template defaults; the earlier DANDI files used 3.815e-7 V.
VOLTS_PER_STEP = 10 / 2**16 / 400

# Probes per rat (Channel_Orderings.pdf and the lab's *_AnimalMetadataText.m files); the first probe is in the left
# hemisphere, the second in the right
PROBES = {
    "Buddy": "Buzsaki64",
    "Gatsby": "Buzsaki64",
    "Achilles": "Buzsaki64sp",
    "Cicero": "Buzsaki64sp",
}
PROBE_DESCRIPTIONS = {
    "Buzsaki64": (
        "NeuroNexus Buzsaki64 silicon probe (BUZ64): 8 shanks, each with 8 recording sites (160 um2), implanted in "
        "the CA1 pyramidal layer of the dorsal hippocampus, parallel to its septo-temporal axis"
    ),
    "Buzsaki64sp": (
        "NeuroNexus Buzsaki64sp silicon probe (BUZ64SP): 6 shanks, each with 10 recording sites (160 um2), and 4 "
        "extra sites spaced every 1.25 mm starting 1.25 mm from the tip of shank 4, implanted in the CA1 pyramidal "
        "layer of the dorsal hippocampus, parallel to its septo-temporal axis"
    ),
}

# Channels of the .eeg files outside the probes (0-based; Channel_Orderings.pdf gives them 1-based)
MISC_CHANNELS = {
    "Buddy": dict(accelerometer=[128, 129, 130], emg=[131]),
    "Gatsby": dict(emg=[128, 129, 130], accelerometer=[131, 132, 133]),
    "Achilles": dict(emg=[128, 129, 130], accelerometer=[131, 132, 133]),
    "Cicero": dict(emg=[128, 129, 130], accelerometer=[131, 132, 133]),
}
# The first three rats' accelerometer supply powered the head-mounted LEDs during the maze (CRCNS hc-11 description)
NO_ACCELEROMETER_ON_MAZE = {"Buddy", "Gatsby", "Achilles"}

MAZE_DESCRIPTIONS = {
    "1.6m Linear Maze": "a wooden 1.6 m linear platform, water-rewarded at both ends",
    "2m Linear Maze": "a 2 m metal linear platform, water-rewarded at both ends",
    "Circular Maze": (
        "a wooden 1 m diameter circular platform, water-rewarded at a predetermined location; the rat was gently "
        "encouraged to run in one direction"
    ),
}


def split_session_id(session_id: str) -> tuple:
    """Return (rat, date) for names like Gatsby_08282013 (MMDDYYYY)."""
    match = re.fullmatch(r"([A-Za-z]+)_(\d{8})", session_id)
    if match is None:
        raise ValueError(f"Unexpected session name {session_id}")
    rat, date = match.groups()
    return rat, datetime.strptime(date, "%m%d%Y")


def read_session_xml(xml_file_path: Path) -> dict:
    """Acquisition settings, anatomical groups with their skip flags, and spike groups of a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    anatomical_groups = [
        [(int(channel.text), channel.get("skip") == "1") for channel in group]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    shank_channels = [
        [int(channel.text) for channel in group.find("channels")]
        for group in root.find("spikeDetection").find("channelGroups").findall("group")
    ]
    return dict(
        n_channels=int(acquisition.find("nChannels").text),
        sampling_rate=float(acquisition.find("samplingRate").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        shank_channels=shank_channels,
        skipped_channels={channel for group in anatomical_groups for channel, skip in group if skip},
    )


def read_sess_info(file_path: Path) -> dict:
    """The lab's <session>_sessInfo.mat (CRCNS hc-11 format), saved either as MATLAB v7.3 (HDF5) or v5."""
    try:
        with h5py.File(file_path, "r") as file:
            sess_info = file["sessInfo"]
            spikes, position, epochs = sess_info["Spikes"], sess_info["Position"], sess_info["Epochs"]
            return dict(
                spike_times=np.ravel(spikes["SpikeTimes"][:]),
                spike_ids=np.ravel(spikes["SpikeIDs"][:]).astype(np.int64),
                pyramidal_ids=np.ravel(spikes["PyrIDs"][:]).astype(np.int64),
                interneuron_ids=np.ravel(spikes["IntIDs"][:]).astype(np.int64),
                position_times=np.ravel(position["TimeStamps"][:]),
                position_xy=np.asarray(position["TwoDLocation"][:]).T,
                position_linear=np.ravel(position["OneDLocation"][:]),
                maze_type="".join(map(chr, np.ravel(position["MazeType"][:]))),
                epochs={name: np.asarray(epochs[name][:]).T for name in epochs},
            )
    except OSError:
        pass
    sess_info = loadmat(str(file_path), simplify_cells=True)["sessInfo"]
    spikes, position, epochs = sess_info["Spikes"], sess_info["Position"], sess_info["Epochs"]
    return dict(
        spike_times=np.ravel(spikes["SpikeTimes"]).astype(float),
        spike_ids=np.ravel(spikes["SpikeIDs"]).astype(np.int64),
        pyramidal_ids=np.ravel(spikes["PyrIDs"]).astype(np.int64),
        interneuron_ids=np.ravel(spikes["IntIDs"]).astype(np.int64),
        position_times=np.ravel(position["TimeStamps"]).astype(float),
        position_xy=np.asarray(position["TwoDLocation"], dtype=float),
        position_linear=np.ravel(position["OneDLocation"]).astype(float),
        maze_type=str(position["MazeType"]),
        epochs={name: np.atleast_2d(np.asarray(value, dtype=float)) for name, value in epochs.items()},
    )


def read_meta(meta_file_path: Path) -> dict:
    """The `key = value` lines of an Amplipex .meta file."""
    meta = {}
    for line in Path(meta_file_path).read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            meta[key.strip()] = value.strip()
    return meta


def recording_start(meta_file_path: Optional[Path]) -> Optional[datetime]:
    """Start date and time of an Amplipex recording from its .meta file."""
    if meta_file_path is None or not Path(meta_file_path).is_file():
        return None
    meta = read_meta(meta_file_path)
    return datetime.strptime(f"{meta['Recording start date']} {meta['Recording start time']}", "%a %b %d %Y %H:%M:%S")
