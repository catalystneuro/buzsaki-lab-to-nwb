"""Helpers for reading the Girardeau et al. 2017 (DANDI:000061) source files on the Buzsaki lab share."""

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree
from scipy.io import loadmat

# The lab's session.mat (CellExplorer) gives the recording system as "Amplipex, KJE-1001 256 Channel system" with a
# least significant bit of 0.3815 uV; the .xml files (20 V range, 16 bits, x1000) would imply 0.305 uV
VOLTS_PER_STEP = 0.3815e-6
# The .whl files: LED positions resampled by the lab to 1250 / 32 Hz, the rate given in the .xml files
WHL_RATE = 1250 / 32
# The paper's 160 recording channels; the .xml files put the accelerometer, air-puff and reward inputs on 160 to 165
N_PROBE_CHANNELS = 160

# The lab's region codes of RecordingLocations.mat (shankInfo). The codes look like the abbreviations of Paxinos and
# Watson's rat brain atlas, which the lab's session.mat files also use (brainRegions_Paximus); the lab has not
# confirmed them. Each code: (location written to the electrodes table, description).
REGION_CODES = {
    "hpc": ("hippocampus", "hippocampus (the dorsal CA1 target of the hippocampal probe, according to the paper)"),
    "bla": (
        "basolateral amygdaloid nucleus",
        "probably Paxinos BLA, basolateral amygdaloid nucleus (anterior part, as the lab's session.mat names it)",
    ),
    "blv": (
        "basolateral amygdaloid nucleus, ventral part",
        "probably Paxinos BLV, basolateral amygdaloid nucleus, ventral part",
    ),
    "bmp": (
        "basomedial amygdaloid nucleus, posterior part",
        "probably Paxinos BMP, basomedial amygdaloid nucleus, posterior part",
    ),
    "ladl": (
        "lateral amygdaloid nucleus, dorsolateral part",
        "probably Paxinos LaDL, lateral amygdaloid nucleus, dorsolateral part",
    ),
    "cen": ("central amygdaloid nucleus", "probably the central amygdaloid nucleus (Paxinos Ce)"),
    "den": ("dorsal endopiriform nucleus", "probably Paxinos DEn, dorsal endopiriform nucleus"),
    "ven": ("ventral endopiriform nucleus", "probably Paxinos VEn, ventral endopiriform nucleus"),
    "pir": ("piriform cortex", "probably Paxinos Pir, piriform cortex"),
    "plc01": (
        "posterolateral cortical amygdaloid nucleus, layer 1",
        "probably Paxinos PLCo1, posterolateral cortical amygdaloid nucleus (area), layer 1",
    ),
    "cpu": ("caudate putamen", "probably Paxinos CPu, caudate putamen (striatum)"),
}
UNKNOWN_REGION = "unknown"


def describe_region_codes(codes) -> str:
    return "; ".join(f"{code}: {REGION_CODES[code][1]}" for code in sorted(codes) if code in REGION_CODES)


def region_location(region: str) -> str:
    """Location for a region value (one code or several joined with '/')."""
    if region == UNKNOWN_REGION:
        return "unknown"
    return " / ".join(REGION_CODES.get(code, (code,))[0] for code in region.split("/"))


def split_session_id(session_id: str) -> tuple:
    """(rat, date) for names like Rat08-20130710."""
    match = re.fullmatch(r"(Rat\d+)-(\d{8})", session_id)
    if match is None:
        raise ValueError(f"Unexpected session name {session_id}")
    return match.group(1), datetime.strptime(match.group(2), "%Y%m%d")


def read_session_xml(xml_file_path: Path) -> dict:
    """Acquisition settings and channel groups from a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    anatomical_groups = [
        [int(channel.text) for channel in group]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    spike_groups = [
        [int(channel.text) for channel in group.find("channels")]
        for group in root.find("spikeDetection").find("channelGroups").findall("group")
    ]
    description = root.find("generalInfo").find("description")
    return dict(
        n_channels=int(acquisition.find("nChannels").text),
        sampling_rate=float(acquisition.find("samplingRate").text),
        voltage_range=float(acquisition.find("voltageRange").text),
        amplification=float(acquisition.find("amplification").text),
        n_bits=int(acquisition.find("nBits").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        anatomical_groups=anatomical_groups,
        spike_groups=spike_groups,
        description=(description.text or "").strip() if description is not None else "",
    )


def shank_channels(xml_info: dict) -> list:
    """Channels of each probe shank: the .xml anatomical groups of the 160 probe channels (0 to 159).

    Anatomical group N is shank N: the shank numbering of RecordingLocations.mat and of the .clu.N/.res.N files, whose
    spike group N holds the channels of anatomical group N (checked), sometimes without a channel the lab left out of
    spike detection (Rat09: channel 123 of shank 16). Rat09 has anatomical groups 17 to 20 (channels 128 to 159, a
    4-shank probe) with no spike groups. The groups of channels 160 to 165 are auxiliary inputs, not electrodes.
    """
    shanks = [list(group) for group in xml_info["anatomical_groups"] if max(group) < N_PROBE_CHANNELS]
    for index, spike_group in enumerate(xml_info["spike_groups"]):
        if not set(spike_group) <= set(shanks[index]):
            raise ValueError(f"Spike group {index + 1} is not within anatomical group {index + 1}")
    return shanks


def read_recording_locations(subject_path: Path, session_id: str) -> dict:
    """Region codes of each shank of a session, from the lab's RecordingLocations.mat (shankInfo).

    shankInfo has a row of region codes and, for each of the rats in its last row, one row of (session, shank) pairs
    per code; the session is the 1-indexed position of the session in the rat's sessions.mat (Sessions.mat) list.
    Returns {shank: [codes]}; shanks absent from the file have no codes.
    """
    rat, _ = split_session_id(session_id)
    shank_info = loadmat(str(subject_path / "RecordingLocations.mat"))["shankInfo"]
    codes = [str(np.asarray(shank_info[0, j]).ravel()[0]) for j in range(shank_info.shape[1])]
    rat_column = codes.index("rat")
    rats = [int(np.asarray(shank_info[row, rat_column]).ravel()[0]) for row in range(1, shank_info.shape[0])]
    row = 1 + rats.index(int(rat.removeprefix("Rat")))

    session_list_path = next(
        path for name in ("sessions.mat", "Sessions.mat") if (path := subject_path / name).is_file()
    )
    mat = loadmat(str(session_list_path), squeeze_me=True)
    sessions = [
        Path(str(path)).name for path in np.atleast_1d(next(v for k, v in mat.items() if not k.startswith("__")))
    ]
    session_index = sessions.index(session_id) + 1

    regions = {}
    for column, code in enumerate(codes):
        if code == "rat":
            continue
        pairs = np.asarray(shank_info[row, column])
        if pairs.ndim != 2 or pairs.shape[1] != 2:
            continue
        for session, shank in pairs:
            if int(session) == session_index:
                regions.setdefault(int(shank), [])
                if code not in regions[int(shank)]:
                    regions[int(shank)].append(code)
    return regions


def read_evt(evt_file_path: Path) -> pd.DataFrame:
    """Lines of a Neuroscope .evt file: time in ms and the text of the event."""
    events = pd.read_csv(evt_file_path, sep="\t", header=None, names=["ms", "text"], dtype={"text": str})
    return events.fillna("")


def load_mat(file_path: Path, **kwargs) -> dict:
    return loadmat(str(file_path), squeeze_me=True, struct_as_record=False, **kwargs)
