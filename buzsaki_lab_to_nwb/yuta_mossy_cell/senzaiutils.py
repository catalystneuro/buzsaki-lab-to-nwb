"""Helpers for reading the Senzai and Buzsaki 2017 (DANDI:000003) source files."""

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

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
        "drd2cellGOOD",
        "pomccell",
        "sstmouse",
        "pomcmouse",
        "drd2mouse",
        "wtmouse",
    ]
    return pd.DataFrame({column: np.asarray(getattr(cell, column)) for column in columns})


def read_exp_sheet(exp_sheet_file_path: Path) -> dict:
    """Rows of the first column of a YM## exp_sheet and the values next to them.

    The mouse's details (genotype, DOB) are on the tab named Sheet1, which is the first tab of every workbook but
    YM39's, where the recording log comes first. The tab with a 'genotype' row is read.
    """
    sheets = pd.read_excel(exp_sheet_file_path, header=None, sheet_name=None)
    rows = {}
    for df in sheets.values():
        if df.shape[1] < 2:
            continue
        rows = {str(key).strip(): value for key, value in zip(df.iloc[:, 0], df.iloc[:, 1]) if isinstance(key, str)}
        if "genotype" in rows:
            break
    return rows


# The paper's Table S1 (16 mice; YM21 is not in the dandiset). SST-Cre mice were injected with a virus, which the
# experiment sheets do not name; the unit summary's `opsin` code agrees with the table (1 for the ChR2 mice, 2 for
# the Arch mice, 0 for the wild-type mouse).
VIRUS_FROM_PAPER = {
    "YutaMouse20": "AAV-DIO-ChR2",
    "YutaMouse23": "AAV-DIO-Arch",
    "YutaMouse37": "AAV-DIO-ChR2",
    "YutaMouse38": "AAV-DIO-ChR2",
    "YutaMouse39": "AAV-DIO-ChR2",
    "YutaMouse40": "AAV-DIO-ChR2",
}
POMC_AI35_MICE_OF_PAPER = ("YutaMouse33", "YutaMouse42", "YutaMouse44")
DRD2_AI35_MICE_OF_PAPER = ("YutaMouse45", "YutaMouse51", "YutaMouse54", "YutaMouse55", "YutaMouse56")
WILD_TYPE_MOUSE_OF_PAPER = "YutaMouse41"
# In the dandiset and in the lab's unit summary, but not in Table S1 or the paper's counts
MICE_NOT_IN_PAPER = ("YutaMouse57",)
NOT_IN_PAPER_NOTE = (
    "This mouse is not part of Senzai and Buzsaki (2017): it is not in the paper's Table S1 and its units are not in "
    "the paper's counts."
)


# The lab's "YutaMouse DG additional channel list.xlsx" (2019) gives the hilus and molecular layer channel of 33
# sessions. It settles the sessions whose dentate spike files name more than one channel, and its one comment says
# that the hilus channel of YutaMouse20-140328 is not in the hilus.
LAB_HILUS_CHANNELS = {"YutaMouse20-140325": 33}
SESSIONS_WITHOUT_A_HILUS_CHANNEL = ("YutaMouse20-140328",)
NOT_HILUS_NOTE = (
    "The lab's channel list says that channel 59, used here as the hilus channel, is not in the hilus, and that the "
    "session should have been removed; one unit of this session is in the paper's data. No channel is marked as the "
    "hilus reference."
)


def hilus_channel(session_id: str, dentate_spike_channels: set) -> Optional[int]:
    """The session's hilus channel: the one channel its dentate spike files name, the channel the lab's list gives
    where they name more than one, and none where the lab's list says the channel is not in the hilus."""
    if session_id in SESSIONS_WITHOUT_A_HILUS_CHANNEL:
        return None
    if session_id in LAB_HILUS_CHANNELS:
        return LAB_HILUS_CHANNELS[session_id]
    return next(iter(dentate_spike_channels)) if len(dentate_spike_channels) == 1 else None


def light_note(mouse: str) -> str:
    """What the paper says about the light delivered to a mouse; the lab's files give no wavelength.

    The paper's STAR Methods name 450 nm (blue) and 520 nm (green) laser diodes, and its figures say which colour each
    group of mice received.
    """
    not_recorded = " The lab's files do not record the wavelength of each laser diode."
    diodes = " The STAR Methods give {nm} nm laser diodes for {colour} light."
    if mouse in VIRUS_FROM_PAPER:
        virus = VIRUS_FROM_PAPER[mouse]
        colour, nm = ("blue", 450) if "ChR2" in virus else ("green", 520)
        group = "SST-Cre mice" if "ChR2" in virus else "the SST-Cre mouse"
        member = "this mouse is one of them" if "ChR2" in virus else "this is that mouse"
        return (
            f"Light colour by the paper's account: {colour}. The paper reports {colour} light for {group} injected "
            f"with {virus} (Figure S1B); {member} (Table S1)." + diodes.format(nm=nm, colour=colour) + not_recorded
        )
    for mice, line, figure in (
        (DRD2_AI35_MICE_OF_PAPER, "DRD2-Cre::Ai35", "Figure 1H and Figure S1D"),
        (POMC_AI35_MICE_OF_PAPER, "POMC-Cre::Ai35", "Figure S1E-G"),
    ):
        if mouse in mice:
            return (
                f"Light colour by the paper's account: green. The paper reports green light for the {line} mice "
                f"({figure}); this mouse is one of them (Table S1)."
                + diodes.format(nm=520, colour="green")
                + not_recorded
            )
    if mouse == WILD_TYPE_MOUSE_OF_PAPER:
        return (
            "Light colour: not stated. This is the paper's wild-type mouse (Table S1), and the paper does not say "
            "which light it received; its STAR Methods give 450 nm (blue) and 520 nm (green) laser diodes."
            + not_recorded
        )
    return (
        "Light colour: not stated. This mouse is not in the paper, whose STAR Methods give 450 nm (blue) and 520 nm "
        "(green) laser diodes and whose figures report green light for its Ai35 mice." + not_recorded
    )


def read_roi(roi_file_path: Path) -> dict:
    """ROIparams of a lab ROI file: where the arena lies in the camera image, in pixels and degrees.

    __EightMazeROI.mat has xc, yc, radius and angle; __OpenFieldROI_<label>.mat has x, y, width and angle, or x, y,
    xwidth, ywidth and angle for the rectangular 'ExtraLarge' arena.
    """
    roi = loadmat(str(roi_file_path), struct_as_record=False, squeeze_me=True)["ROIparams"]
    return {name: float(getattr(roi, name)) for name in roi._fieldnames}


def roi_parts(roi: dict) -> tuple:
    """Names of the ROI's origin (x, y) and of its size along each axis, and what the ROI outlines."""
    if "radius" in roi:
        return ("xc", "yc"), ("radius", "radius"), "the circle formed by the side arms"
    if "width" in roi:
        return ("x", "y"), ("width", "width"), "the arena, whose side spans the width"
    return ("x", "y"), ("xwidth", "ywidth"), "the arena, whose sides span xwidth and ywidth"


def pixels_to_arena(pixels: np.ndarray, roi: dict) -> np.ndarray:
    """The lab's arena coordinates (twhl_norm) of LED positions in camera pixels.

    The pixel offset from the ROI's corner (open field: x, y) or centre (T-maze: xc, yc) is turned by the ROI's angle
    and divided by its size (open field: width, or xwidth and ywidth; T-maze: radius). This reproduces the lab's
    position files from the .whl file to rounding error, which is how the formula was found.
    """
    origin, sizes, _ = roi_parts(roi)
    angle = np.radians(roi["angle"])
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    offset = np.asarray(pixels, dtype=float) - np.array([roi[origin[0]], roi[origin[1]]])
    return offset @ rotation.T / np.array([roi[sizes[0]], roi[sizes[1]]])


def roi_note(roi: dict, roi_file_name: str, frame_offset: Optional[int] = None) -> str:
    """Sentences for a position series: where its arena lies in the camera image, and, when `frame_offset` is given
    (the formula was checked against the session's .whl file), how the series follows from LED 0's pixels."""
    origin, sizes, what = roi_parts(roi)
    names = list(origin) + list(dict.fromkeys(sizes))
    numbers = [f"{name} = {roi[name]:.2f}" for name in names]
    note = (
        f"In the camera image, the lab's region of interest for {what} ({roi_file_name}) has "
        + ", ".join(numbers[:-1])
        + f" and {numbers[-1]} pixels, at an angle of {roi['angle']:.2f} degrees"
    )
    if frame_offset is None:
        return note
    frames = {0: "at the same time", -1: "one video frame (25.6 ms) earlier", 1: "one video frame (25.6 ms) later"}
    return note + (
        f". With (dx, dy) the pixel position of LED 0 (led0_position) minus ({origin[0]}, {origin[1]}), this series "
        f"is ((dx cos(angle) - dy sin(angle)) / {sizes[0]}, (dx sin(angle) + dy cos(angle)) / {sizes[1]}), and its "
        f"sample at time t is the led0_position sample {frames[frame_offset]}"
    )


def find_frame_offset(times: np.ndarray, arena: np.ndarray, led_pixels: np.ndarray, roi: dict, rate: float):
    """The offset in video frames (-1, 0 or 1) at which `pixels_to_arena` of the .whl LED 0 positions gives the lab's
    arena positions, or None when no offset does (then the formula is not stated in the file)."""
    rows = np.rint(np.asarray(times) * rate).astype(int)
    for offset in (-1, 0, 1):
        shifted = rows + offset
        inside = (shifted >= 0) & (shifted < len(led_pixels))
        expected = pixels_to_arena(led_pixels[shifted[inside]], roi)
        seen = ~np.isnan(expected).any(axis=1) & ~np.isnan(arena[inside]).any(axis=1)
        if seen.sum() >= 0.9 * inside.sum() > 0 and np.allclose(expected[seen], arena[inside][seen], atol=1e-6):
            return offset
    return None


def open_published(path) -> "h5py.File":
    """The session's earlier DANDI file: a local path, or a URL streamed with remfile (some are too large to download
    next to the output on a cloud job's disk)."""
    import h5py

    if str(path).startswith(("https://", "http://")):
        import remfile

        return h5py.File(remfile.File(str(path)), "r")
    return h5py.File(path, "r")
