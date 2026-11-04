"""Helpers for reading the Fujisawa et al. 2008 (DANDI:000067) source files.

The sessions, their tasks and the channel map are from the CRCNS pfc-2 data description (version 0.6), corrected
where the session .xml files disagree with it.
"""

from pathlib import Path

import numpy as np
from lxml import etree

# Session: (day folder, state, duration in minutes), from the session table of the CRCNS pfc-2 data description
SESSIONS = {
    "EE.042": ("EE0622", "sleep", 16.55),
    "EE.043": ("EE0622", "test", 0.03),
    "EE.044": ("EE0622", "test", 0.02),
    "EE.045": ("EE0622", "spontaneous alternation task", 39.01),
    "EE.046": ("EE0622", "sleep", 2.33),
    "EE.047": ("EE0622", "sleep", 20.17),
    "EE.048": ("EE0622", "sleep", 17.26),
    "EE.049": ("EE0622", "working memory task", 29.81),
    "EE.050": ("EE0622", "sleep", 31.27),
    "EE.080": ("EE0627", "sleep", 14.59),
    "EE.081": ("EE0627", "sleep", 2.91),
    "EE.082": ("EE0627", "sleep", 22.23),
    "EE.083": ("EE0627", "spontaneous alternation task", 22.66),
    "EE.084": ("EE0627", "sleep", 28.41),
    "EE.085": ("EE0627", "sleep", 11.49),
    "EE.086": ("EE0627", "sleep", 2.53),
    "EE.087": ("EE0627", "sleep", 7.48),
    "EE.088": ("EE0627", "working memory task", 36.09),
    "EE.089": ("EE0627", "sleep", 34.3),
    "EE.152": ("EE0705", "working memory task", 42.54),
    "EE.165": ("EE0706", "working memory task", 49.06),
    "EE.188": ("EE0708", "working memory task", 46.87),
    "EE.196": ("EE0710", "working memory task", 47.4),
    "EE.210": ("EE0711", "working memory task", 40.2),
    "FF.103": ("FF1114", "working memory task", 49.2),
    "FF.130": ("FF1116", "working memory task", 34.84),
    "FF.167": ("FF1119", "working memory task", 33.94),
    "GG.063": ("GG0330", "spontaneous alternation task", 47.51),
    "GG.069": ("GG0330", "working memory task", 39.6),
    "GG.097": ("GG0401", "working memory task", 29.17),
    "GG.149": ("GG0406", "working memory task", 47.44),
}

PFC_SHANKS = range(1, 9)  # 64 channels of a Buzsaki64 probe in the medial prefrontal cortex
CA1_SHANKS = range(9, 13)  # 32 channels of a Buzsaki32 probe in the intermediate CA1

# The 13th channel group of each .xml: the non-neural inputs, 1-based channel: description. For rats EE and FF
# (104 channels) from the CRCNS description; for rat GG (101 channels), whose .xml puts these inputs on 65-69, the
# sensor sides are from the trials (channel 65 is active on Left trials and 66 on Right trials) and the order of the
# other three is not documented.
AUXILIARY_CHANNELS = {
    "EE": {
        97: "optic sensor for nose-poke detection (Right trials)",
        98: "optic sensor for nose-poke detection (Left trials)",
        99: "not in use",
        100: "not in use",
        101: "encoder signal 1 of the running wheel (spontaneous alternation task)",
        102: "encoder signal 2 of the running wheel (spontaneous alternation task)",
        103: "not in use",
        104: "sync signal",
    },
    "GG": {
        65: "optic sensor for nose-poke detection (Left trials)",
        66: "optic sensor for nose-poke detection (Right trials)",
        67: "a wheel encoder or sync input (not documented which)",
        68: "a wheel encoder or sync input (not documented which)",
        69: "a wheel encoder or sync input (not documented which)",
    },
}
AUXILIARY_CHANNELS["FF"] = AUXILIARY_CHANNELS["EE"]


def subject_of(session_id: str) -> str:
    return session_id.split(".")[0]


def read_channel_groups(xml_file_path: Path) -> dict:
    """Number of channels and the 0-based channels of each anatomical group of a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    groups = [
        [int(channel.text) for channel in group.findall("channel")]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    return dict(n_channels=int(root.find("acquisitionSystem").find("nChannels").text), groups=groups)


def region_of_shank(shank: int) -> str:
    if shank in PFC_SHANKS:
        return "mPFC"
    if shank in CA1_SHANKS:
        return "CA1"
    return "none"


def read_clusters(session_path: Path, shank: int) -> tuple:
    """Cluster of each spike (the .clu file's first line is the number of clusters) and its time in samples."""
    session_id = session_path.name
    clusters = np.loadtxt(session_path / f"{session_id}.clu.{shank}", dtype=np.int64, ndmin=1)[1:]
    samples = np.loadtxt(session_path / f"{session_id}.res.{shank}", dtype=np.int64, ndmin=1)
    if len(clusters) != len(samples):
        raise ValueError(f"{session_id} shank {shank}: {len(clusters)} clusters for {len(samples)} spikes")
    return clusters, samples


def behavior_files(session_path: Path) -> dict:
    """The session's behavior files: 'all' for XXX_Behavior.mat, 'mPFC' and 'CA1' for the per-region files."""
    session_id = session_path.name
    compact = session_id.replace(".", "")
    found = {}
    for key, name in (
        ("all", f"{session_id}_Behavior.mat"),
        ("mPFC", f"{compact}_Behavior_PFC.mat"),
        ("CA1", f"{compact}_Behavior_CA1.mat"),
        ("example", f"{compact}_example.mat"),
    ):
        if (session_path / name).is_file():
            found[key] = session_path / name
    return found
