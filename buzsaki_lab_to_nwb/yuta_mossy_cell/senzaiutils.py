"""Helpers for reading the Senzai and Buzsaki 2017 (DANDI:000003) source files."""

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree
from scipy.io import loadmat

# fineCellType codes of the DG_all_6 unit summary
FINE_CELL_TYPES = {
    0: "unclassified",
    2: "mossy cell",
    3: "narrow-waveform interneuron",
    4: "optogenetically tagged SST interneuron",
    5: "wide-waveform interneuron (narrower)",
    6: "wide-waveform interneuron (wider)",
    8: "positive-waveform unit (non-bursty)",
    9: "positive-waveform unit (bursty)",
    10: "positive-negative-waveform unit",
}
# region codes of the DG_all_6 unit summary
REGIONS = {3: "CA3", 4: "DG"}


def split_session_id(session_id: str) -> tuple:
    """Return (mouse, date, is_second_probe) for names like YutaMouse41-150829 or YutaMouse51b160514."""
    match = re.fullmatch(r"(YutaMouse\d+)(-|b)(\d{6})", session_id)
    if match is None:
        raise ValueError(f"Unexpected session name {session_id}")
    mouse, separator, date = match.groups()
    return mouse, datetime.strptime(date, "%y%m%d"), separator == "b"


def read_session_xml(xml_file_path: Path) -> dict:
    """Acquisition settings and spike-detection channel groups from a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    shank_channels = [
        [int(channel.text) for channel in group.find("channels")]
        for group in root.find("spikeDetection").find("channelGroups").findall("group")
    ]
    return dict(
        n_channels=int(acquisition.find("nChannels").text),
        sampling_rate=float(acquisition.find("samplingRate").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        spikes_n_samples=int(root.find("neuroscope").find("spikes").find("nSamples").text),
        shank_channels=shank_channels,
    )


@lru_cache
def read_unit_summary(summary_file_path: Path) -> pd.DataFrame:
    """The per-unit table of DG_all_6__UnitFeatureSummary_add.mat, one row per unit of the paper's sessions."""
    cell = loadmat(str(summary_file_path), struct_as_record=False, squeeze_me=True)["UnitFeatureCell"]
    columns = [
        "fname",
        "unitID",
        "shank",
        "unitIDshank",
        "fineCellType",
        "region",
        "ACGquality",
        "UnitStability",
        "sstcell",
        "drd2cell",
        "pomccell",
        "sstmouse",
        "pomcmouse",
        "drd2mouse",
        "wtmouse",
    ]
    return pd.DataFrame({column: np.asarray(getattr(cell, column)) for column in columns})


def read_exp_sheet(exp_sheet_file_path: Path) -> dict:
    """Rows of the first column of a YM## exp_sheet and the values next to them."""
    df = pd.read_excel(exp_sheet_file_path, header=None)
    return {str(key).strip(): value for key, value in zip(df.iloc[:, 0], df.iloc[:, 1]) if isinstance(key, str)}


def open_published(path) -> "h5py.File":
    """The session's earlier DANDI file: a local path, or a URL streamed with remfile (some are too large to download
    next to the output on a cloud job's disk)."""
    import h5py

    if str(path).startswith(("https://", "http://")):
        import remfile

        return h5py.File(remfile.File(str(path)), "r")
    return h5py.File(path, "r")
