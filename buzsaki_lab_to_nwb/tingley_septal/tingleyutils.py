"""Helpers for reading the Tingley and Buzsaki 2018/2020 (DANDI:000213, DANDI:000218) source files."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from lxml import etree
from scipy.io import loadmat
from scipy.io.matlab import mat_struct

# Intan RHD2000 amplifiers: 0.195 uV per step
VOLTS_PER_STEP = 0.195e-6


def _from_scipy(value):
    if isinstance(value, mat_struct):
        return {name: _from_scipy(getattr(value, name)) for name in value._fieldnames}
    if isinstance(value, np.ndarray) and value.dtype == object:
        return [_from_scipy(item) for item in value.ravel()]
    if isinstance(value, np.ndarray) and value.dtype.kind == "U":
        return str(value) if value.ndim == 0 else [str(item) for item in value.ravel()]
    return value


def _from_hdf5(file: h5py.File, node):
    """A MATLAB v7.3 value: structs become dicts, cells lists, char arrays strings and numeric arrays numpy arrays."""
    if isinstance(node, h5py.Group):
        return {name: _from_hdf5(file, node[name]) for name in node if not name.startswith("#")}
    matlab_class = node.attrs.get("MATLAB_class", b"").decode()
    if node.attrs.get("MATLAB_empty", 0):
        return [] if matlab_class == "cell" else np.array([])
    data = node[()]
    if matlab_class == "cell":
        return [_from_hdf5(file, file[reference]) for reference in np.ravel(data.T)]
    if matlab_class == "char":
        return "".join(map(chr, np.ravel(data.T)))
    if matlab_class == "logical":
        data = data.astype(bool)
    data = np.asarray(data).T  # MATLAB is column-major
    if data.ndim == 2 and 1 in data.shape:
        data = data.ravel()
    if data.size == 1:
        return data.ravel()[0]
    return data


def read_mat(file_path: Path) -> dict:
    """The variables of a MATLAB file, saved either as v5 (scipy) or v7.3 (HDF5)."""
    try:
        mat = loadmat(str(file_path), squeeze_me=True, struct_as_record=False)
    except NotImplementedError:
        with h5py.File(file_path, "r") as file:
            return {name: _from_hdf5(file, file[name]) for name in file if not name.startswith("#")}
    return {name: _from_scipy(value) for name, value in mat.items() if not name.startswith("__")}


def as_list(value) -> list:
    """A MATLAB value that may be a scalar, a string, an array or a cell, as a list."""
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        return [value]
    if isinstance(value, list):
        return value
    return list(np.atleast_1d(value))


def as_intervals(value) -> np.ndarray:
    """An n x 2 array of intervals (MATLAB stores a single interval as a 2-vector and none as an empty array)."""
    array = np.asarray(value, dtype=float)
    if array.size == 0:
        return np.zeros((0, 2))
    return array.reshape(-1, 2)


def read_session_xml(xml_file_path: Path) -> dict:
    """Acquisition settings and spike groups of a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    shank_channels = [
        [int(channel.text) for channel in group.find("channels")]
        for group in root.find("spikeDetection").find("channelGroups").findall("group")
    ]
    anatomical_groups = [
        [(int(channel.text), channel.get("skip") == "1") for channel in group]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    return dict(
        n_channels=int(acquisition.find("nChannels").text),
        sampling_rate=float(acquisition.find("samplingRate").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        shank_channels=shank_channels,
        anatomical_channels=[[channel for channel, _ in group] for group in anatomical_groups],
        skipped_channels={channel for group in anatomical_groups for channel, skip in group if skip},
    )


def split_session_id(session_id: str) -> dict:
    """Date, start time (if the name has one), the depths in the name and whether it is a merged session.

    Names are DT2_rPPC_rCCG_<depth>um_<depth>um_<YYYYMMDD>_<YYMMDD>_<HHMMSS>, DT1_rLS_<YYYYMMDD>_<depth>um, and
    <YYYYMMDD>_<depth>um_<depth>um_<YYMMDD>_<HHMMSS> or <YYYYMMDD>_<depth>um_<depth>um_merge for the other rats.
    """
    date = re.search(r"(?:^|_)(20\d{6})(?:_|$)", session_id).group(1)
    if date == "20170229":
        date = "20170228"  # 2017 was not a leap year
    time_match = re.search(r"_(\d{6})_(\d{6})$", session_id)
    start = datetime.strptime(
        date + (time_match.group(2) if time_match else ""), "%Y%m%d%H%M%S" if time_match else "%Y%m%d"
    )
    return dict(
        date=datetime.strptime(date, "%Y%m%d"),
        start=start if time_match else None,
        depths=[int(depth) for depth in re.findall(r"(\d+)um", session_id)],
        merged=session_id.endswith("_merge"),
    )


def merged_session_start(session_path: Path) -> Optional[datetime]:
    """Start of the first recording of a merged session, from its recording subfolders (<...>_<YYMMDD>_<HHMMSS>)."""
    starts = []
    for path in Path(session_path).iterdir():
        match = re.search(r"_(\d{6})_(\d{6})$", path.name)
        if path.is_dir() and match:
            starts.append(datetime.strptime("".join(match.groups()), "%y%m%d%H%M%S"))
    return min(starts) if starts else None


def channels_of(value) -> list:
    """0-based channel numbers from a sessionInfo or event-file field (a scalar, an array or empty)."""
    return [int(channel) for channel in np.atleast_1d(np.asarray(value, dtype=float)).ravel() if np.isfinite(channel)]


def read_clu_res(session_path: Path, session_id: str, n_groups: int) -> dict:
    """Map (spike group, cluster) to spike samples for clusters 2 and up of the .clu.N/.res.N files."""
    units = {}
    for group in range(1, n_groups + 1):
        clu_file_path = session_path / f"{session_id}.clu.{group}"
        res_file_path = session_path / f"{session_id}.res.{group}"
        if not clu_file_path.is_file() or not res_file_path.is_file():
            continue
        clusters = np.loadtxt(clu_file_path, dtype=np.int64, ndmin=1)[1:]  # the first line is the number of clusters
        samples = np.loadtxt(res_file_path, dtype=np.int64, ndmin=1)
        if len(clusters) != len(samples):
            raise ValueError(f"{clu_file_path.name} and {res_file_path.name} have different lengths")
        for cluster in np.unique(clusters[clusters > 1]):
            units[(group, int(cluster))] = samples[clusters == cluster]
    return units


def find_file(session_path: Path, *names: str) -> Optional[Path]:
    """The first of `names` that exists in the session folder."""
    for name in names:
        if (session_path / name).is_file():
            return session_path / name
    return None


# The lab's region labels (sessionInfo.region, spikes.cellinfo.region) and the structure each one names
REGION_NAMES = {
    "ls": "lateral septal nucleus",
    "hpc": "hippocampal formation",  # the lab's label for the probe aimed at dorsal CA1; not resolved to a subfield
    "ca1": "CA1 field of hippocampus",
    "ca3": "CA3 field of hippocampus",
    "ppc": "posterior parietal cortex",
    "acg": "anterior cingulate cortex",
    "cc": "corpus callosum",
    "ms": "medial septal nucleus",
    "sFi": "septofimbrial nucleus",
}

# The lab's event files of ripples and LS high-frequency oscillations: (file suffix, table name, what they are)
EVENT_FILES = (
    ("ripplesALL.event.mat", "ripplesALL", "hippocampal ripples"),
    ("ripplesNREM.event.mat", "ripplesNREM", "hippocampal ripples, detection restricted to NREM sleep"),
    ("ripplesWAKE.event.mat", "ripplesWAKE", "hippocampal ripples, detection restricted to wake"),
    ("CA1Ripples.events.mat", "CA1Ripples", "CA1 ripples"),
    ("LSRipples.events.mat", "LSRipples", "lateral septum high-frequency oscillations (HFOs)"),
    ("ls_ripples.event.mat", "ls_ripples", "lateral septum high-frequency oscillations (HFOs), an earlier detection"),
)
# ripples_ls.mat: an older detection of LS events, an n x 4 array of [start, peak, stop, normalized peak power]
OLD_LS_EVENT_FILE = "ripples_ls.mat"


def matlab_datenum_to_date(datenum: float) -> str:
    """A MATLAB datenum (days from the year 0) as an ISO date."""
    return datetime.fromordinal(int(datenum) - 366).date().isoformat()


def read_event_files(session_path: Path, session_id: str) -> list:
    """The ripple and HFO detections of the session, each a dict with the table name, the events and the detector."""
    tables = []
    for suffix, name, what in EVENT_FILES:
        file_path = Path(session_path) / f"{session_id}.{suffix}"
        if not file_path.is_file():
            continue
        mat = read_mat(file_path)
        ripples = mat["ripples"] if "ripples" in mat else next(iter(mat.values()))
        info = ripples.get("detectorinfo", {})
        parameters = dict(
            info.get("detectionparms") or ripples.get("detectorParams") or ripples.get("detectorparms") or {}
        )
        parameters.pop("lfp", None)  # the detection channel's LFP, the same as the LFP of the file
        data = ripples.get("data", {})
        intervals = as_intervals(ripples.get("timestamps", ripples.get("times")))
        tables.append(
            dict(
                name=name,
                file_name=file_path.name,
                what=what,
                intervals=intervals,
                peaks=np.asarray(ripples["peaks"], dtype=float).ravel(),
                peak_normed_power=np.asarray(ripples["peakNormedPower"], dtype=float).ravel(),
                peak_frequency=(
                    np.asarray(data["peakFrequency"], dtype=float).ravel() if "peakFrequency" in data else None
                ),
                peak_amplitude=(
                    np.asarray(data["peakAmplitude"], dtype=float).ravel() if "peakAmplitude" in data else None
                ),
                ripple_channel=channels_of(ripples.get("rippleChan", [])),
                noise_channel=channels_of(ripples.get("refChan", [])),
                detector=info.get("detectorname", ripples.get("detectorName", "")),
                detection_date=info.get("detectiondate"),
                parameters=parameters,
                stdev=ripples.get("stdev"),
                n_noise=len(as_intervals(ripples.get("noise", {}).get("times", []))),
            )
        )
    file_path = Path(session_path) / OLD_LS_EVENT_FILE
    if file_path.is_file():
        mat = read_mat(file_path)
        events = np.asarray(mat["ripples_ls"], dtype=float).reshape(-1, 4)
        tables.append(
            dict(
                name="ripples_ls",
                file_name=file_path.name,
                what="lateral septum high-frequency oscillations (HFOs), the lab's oldest detection",
                intervals=events[:, [0, 2]],
                peaks=events[:, 1],
                peak_normed_power=events[:, 3],
                peak_frequency=None,
                peak_amplitude=None,
                ripple_channel=[],
                noise_channel=[],
                detector="",
                detection_date=None,
                parameters={},
                stdev=mat.get("stdev_ls"),
                n_noise=len(as_intervals(mat.get("noise_ls", []))),
            )
        )
    return tables


def read_session_info(session_path: Path, session_id: str) -> Optional[dict]:
    """The fields of <session>.sessionInfo.mat the conversion uses; None if the session has no such file.

    Channel numbers are 0-based, as in the lab's files: sessionInfo.ca1 of DT2 0221 (116) is the rippleChan of its
    CA1Ripples file, and sessionInfo.ls of DT8 0207 (25) the rippleChan of its LSRipples file.
    """
    file_path = Path(session_path) / f"{session_id}.sessionInfo.mat"
    if not file_path.is_file():
        return None
    session_info = read_mat(file_path)["sessionInfo"]
    region = [str(label) for label in as_list(session_info.get("region"))]
    depth = session_info.get("depth")
    return dict(
        region=region or None,
        theta=channels_of(session_info.get("thetaChans", [])),
        lfp=channels_of(session_info.get("lfpChans", [])),
        ca1=channels_of(session_info.get("ca1", [])),
        ca3=channels_of(session_info.get("ca3", [])),
        ls=channels_of(session_info.get("ls", [])),
        ref=channels_of(session_info.get("refChan", [])),
        depth=float(depth) if depth is not None and np.size(depth) == 1 else None,
        animal=session_info.get("animal"),
    )
