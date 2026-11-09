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
# The paper's 160 recording channels (Rat10 also has 6 hippocampal wires, on 160 to 165)
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


def wire_groups(description: str) -> dict:
    """Recording wires named in an .xml description: {channels: region code or None}.

    Rat10's .xml says "Hippo wires -  160-165" (0-indexed channels, like its "Amygdala Right - voies 0-63").
    """
    wires = {}
    for line in description.splitlines():
        match = re.search(r"wires\s*-\s*(\d+)\s*-\s*(\d+)", line, flags=re.IGNORECASE)
        if match:
            channels = tuple(range(int(match.group(1)), int(match.group(2)) + 1))
            wires[channels] = "hpc" if re.search(r"hippo", line, flags=re.IGNORECASE) else None
    return wires


def electrode_groups(xml_info: dict, auxiliary_channels: set) -> list:
    """The .xml anatomical groups that are electrodes, as (group number, channels, kind).

    Anatomical group N is shank N: the shank numbering of RecordingLocations.mat and (but for Rat09-20140324, see
    spike_group_shanks) of the .clu.N/.res.N files, whose spike group N holds the channels of anatomical group N,
    sometimes without a channel the lab left out of spike detection (Rat09: channel 123 of shank 16). A group is
    left out when it holds auxiliary inputs (the session's channel tags), or when it has no spike group and only
    channels from 160 up (beyond the paper's 160 probe channels) and the .xml description does not name it as
    recording wires (Rat11: groups 21 and 22, channels 160 to 165, which the source does not identify). Kept without
    spike groups: Rat09's groups 17 to 20 (channels 128 to 159, a 4-shank probe) and Rat10's group 21 (channels 160
    to 165, "Hippo wires" in its .xml). kind is "shank" or "wires".
    """
    wires = {frozenset(channels) for channels in wire_groups(xml_info["description"])}
    groups = []
    with_spike_groups = set(spike_group_shanks(xml_info).values())
    for number, channels in enumerate(xml_info["anatomical_groups"], start=1):
        if set(channels) & auxiliary_channels:
            continue
        has_spike_group = number in with_spike_groups
        if frozenset(channels) in wires:
            groups.append((number, list(channels), "wires"))
        elif has_spike_group or min(channels) < N_PROBE_CHANNELS:
            groups.append((number, list(channels), "shank"))
    kept = {number for number, _, _ in groups}
    for index, number in spike_group_shanks(xml_info).items():
        if number not in kept:
            raise ValueError(f"Spike group {index} is in anatomical group {number}, which is not an electrode group")
    return groups


def spike_group_shanks(xml_info: dict) -> dict:
    """The anatomical group (shank) of each spike group N, the N of the .clu.N/.res.N files: the one group that holds
    its channels. That is group N, except in Rat09-20140324, whose spike groups 17 to 19 are anatomical groups 18 to 20
    (group 17 has no spike group there; RecordingLocations.mat places shanks 17 to 20 all in hpc that session)."""
    shanks = {}
    for index, spike_group in enumerate(xml_info["spike_groups"], start=1):
        holders = [
            number
            for number, channels in enumerate(xml_info["anatomical_groups"], start=1)
            if set(spike_group) <= set(channels)
        ]
        if len(holders) != 1:
            raise ValueError(f"Spike group {index} is not within exactly one anatomical group")
        shanks[index] = holders[0]
    return shanks


def read_session_list(subject_path: Path, rat: str) -> list:
    """The rat's session names in order: sessions.mat or Sessions.mat, else the text file RatNN-SessionList (Rat10)."""
    for name in ("sessions.mat", "Sessions.mat"):
        if (subject_path / name).is_file():
            mat = loadmat(str(subject_path / name), squeeze_me=True)
            paths = np.atleast_1d(next(v for k, v in mat.items() if not k.startswith("__")))
            return [Path(str(path)).name for path in paths]
    lines = (subject_path / f"{rat}-SessionList").read_text().split()
    return [Path(line).name for line in lines]


def read_recording_locations(subject_path: Path, session_id: str) -> dict:
    """Region codes of each shank of a session, from the lab's RecordingLocations.mat (shankInfo).

    shankInfo has a row of region codes and, for each of the rats in its last row, one row of (session, shank) pairs
    per code; the session is the 1-indexed position of the session in the rat's sessions.mat (Sessions.mat, or RatNN-SessionList) list.
    Returns {shank: [codes]}; shanks absent from the file have no codes.
    """
    rat, _ = split_session_id(session_id)
    shank_info = loadmat(str(subject_path / "RecordingLocations.mat"))["shankInfo"]
    codes = [str(np.asarray(shank_info[0, j]).ravel()[0]) for j in range(shank_info.shape[1])]
    rat_column = codes.index("rat")
    rats = [int(np.asarray(shank_info[row, rat_column]).ravel()[0]) for row in range(1, shank_info.shape[0])]
    row = 1 + rats.index(int(rat.removeprefix("Rat")))

    sessions = read_session_list(subject_path, rat)
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


def read_cell_types(subject_path: Path, session_id: str, n_units: int) -> tuple:
    """The paper's cell type of each unit of a session (in shank and cluster order), from the lab's RatNN-finalType.mat,
    and a note for the units table; (None, note) where the source does not type the session's units (see
    cell_types.yaml)."""
    import yaml

    rat, _ = split_session_id(session_id)
    table = yaml.safe_load((Path(__file__).parent / "cell_types.yaml").read_text())
    days, codes = table["finaltype_days"].get(rat), {int(k): v for k, v in table["codes"].items()}
    final_type_path = subject_path / f"{rat}-finalType.mat"
    if session_id in table["untyped_days"]:
        return None, f" No cell types: {table['untyped_days'][session_id]}."
    if days is None or session_id not in days or not final_type_path.is_file():
        return None, f" No cell types: the lab's share has no {rat}-finalType.mat for this rat."
    if days[session_id] != n_units:
        raise ValueError(f"{session_id} has {n_units} units, but {days[session_id]} in the lab's finalType order")
    final_type = np.asarray(loadmat(str(final_type_path), squeeze_me=True)["finalType"]).ravel()
    start = sum(n for day, n in days.items() if day < session_id)
    if list(days) != sorted(days) or start + n_units > final_type.size:
        raise ValueError(f"{rat}-finalType.mat does not cover the units of {session_id}")
    return [codes[int(code)] for code in final_type[start : start + n_units]], ""
