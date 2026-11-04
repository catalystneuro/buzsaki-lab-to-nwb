"""Epochs, sleep states, position, head direction and detected events of a Peyrache session (DANDI:000056)."""

import re
from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.behavior import CompassDirection, Position, SpatialSeries
from pynwb.epoch import TimeIntervals

from .peyracheutils import (
    BEHAVIOR_EPOCHS,
    POSITION_RATE,
    interval_set,
    load_mat,
    read_columns,
    read_dat_segments,
    read_events,
)

PAPER_STATES = {
    "wake": (
        "Wake",
        "the open-field exploration epoch, which the paper's analyses use as wake (.states.Wake; it equals the "
        "lab's wakeEp)",
    ),
    "SWS": ("SWS", "slow-wave sleep scored by the lab for the paper (.states.SWS)"),
    "REM": ("REM", "REM sleep scored by the lab for the paper (.states.REM)"),
}
BUZCODE_STATES = {
    "WAKEstate": "wake, scored by the lab's 2019 buzcode SleepScoreMaster (all waking, not only the open field)",
    "NREMstate": "non-REM sleep, scored by the lab's 2019 buzcode SleepScoreMaster",
    "REMstate": "REM sleep, scored by the lab's 2019 buzcode SleepScoreMaster",
}
VIDEO_NOTE = (
    " The LEDs were filmed at 30 frames per second, detected online and resampled at 39.0625 Hz by the acquisition "
    "system; according to the paper the first video frame is misaligned by a random 0-60 ms, the rate being accurate "
    "thereafter."
)
# Sessions whose data need a note; the data are kept as the lab gives them
POSITION_NOTES = {
    "Mouse12-120808": (
        " In this session the position and the spikes do not share a clock in sub-recording 03 (the open field, about "
        "6666 to 8582 s): the head-direction tuning of the thalamic HD cells is sharpest when the position is shifted "
        "by -2.0 s at the start of the sub-recording to -3.5 s at its end, while the other sub-recordings line up. "
        "No sync or video timestamp file is on the lab's share, and the lab left this session out of its own list of "
        "AD sessions (datasets_Adn.list). The data are written as the lab gives them, without correction."
    ),
}
EPOCH_NOTES = {
    "Mouse12-120808": (
        " In this session the lab's wakeEp (and .states.Wake) holds 22297 to 25036 s, sub-recordings 09 to 11 of its "
        "radEp, while its wakeEpIx lists sub-recording 03, the open field. This matches the paper's Methods: 'In one "
        "session, the exploration of a radial maze following the second sleep phase was considered as the wake "
        "period'. Both are written as the lab gives them."
    ),
}


class PeyracheBehaviorInterface(BaseDataInterface):
    """Epochs, sleep states, LED positions, head direction, and the lab's down states and ripples."""

    def __init__(self, folder_path: DirectoryPath, mouse_folder_path: Optional[DirectoryPath] = None, verbose=False):
        super().__init__(folder_path=folder_path, mouse_folder_path=mouse_folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def file(self, suffix: str) -> Path:
        """A session file, looked for in the session folder, then in the mouse folder (Mouse25 keeps some there)."""
        file_path = self.session_path / f"{self.session_id}{suffix}"
        mouse_folder_path = self.source_data["mouse_folder_path"]
        if not file_path.is_file() and mouse_folder_path is not None:
            alternative = Path(mouse_folder_path) / f"{self.session_id}{suffix}"
            if alternative.is_file():
                return alternative
        return file_path

    def general_info(self) -> dict:
        file_path = self.session_path / "Analysis" / "GeneralInfo.mat"
        return load_mat(file_path) if file_path.is_file() else {}

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        self.add_epochs(nwbfile)
        self.add_paper_states(nwbfile)
        self.add_buzcode_states(nwbfile)
        self.add_positions(nwbfile)
        self.add_down_states(nwbfile)
        self.add_ripples(nwbfile)

    def add_epochs(self, nwbfile: NWBFile):
        segments = read_dat_segments(self.session_path) if (self.session_path / "DatSegments.txt").is_file() else []
        if segments:
            table = TimeIntervals(
                name="sub_recordings",
                description=(
                    "the session's sub-recordings (-NN.dat files), concatenated in order from time 0 for spike sorting; "
                    "boundaries from the lengths in DatSegments.txt (1250 Hz samples) and names from the .srs file"
                ),
            )
            table.add_column(name="file_name", description="name of the sub-recording's .dat file, without extension")
            for name, start, stop in segments:
                table.add_row(start_time=start, stop_time=stop, file_name=name)
            nwbfile.add_time_intervals(table)

        epochs_file_path = self.session_path / "Analysis" / "BehavEpochs.mat"
        if not epochs_file_path.is_file():
            return
        mat = load_mat(epochs_file_path)
        rows, notes = [], []
        for lab_name, (tag, _) in BEHAVIOR_EPOCHS.items():
            if lab_name not in mat:
                continue
            intervals = interval_set(mat[lab_name])
            indices = [int(index) for index in np.atleast_1d(mat.get(lab_name + "Ix", 0)) if int(index) > 0]
            names = [segments[index - 1][0] for index in indices if index <= len(segments)]
            for start, stop in intervals:
                overlapped = [name for name, seg_start, seg_stop in segments if seg_start < stop and seg_stop > start]
                rows.append((start, stop, tag, lab_name, ", ".join(overlapped), ", ".join(names)))
            if indices and segments and len(intervals):
                expected = sorted((segments[index - 1][1], segments[index - 1][2]) for index in indices)
                covered = all(
                    any(abs(start - seg_start) < 0.01 and stop <= seg_stop + 0.01 for seg_start, seg_stop in expected)
                    for start, stop in intervals
                )
                if not covered:
                    notes.append(
                        f"the intervals of {lab_name} are not those of the sub-recordings its {lab_name}Ix lists"
                    )
        if not rows:
            return
        present = sorted({row[2] for row in rows}, key=lambda tag: [t for t, _ in BEHAVIOR_EPOCHS.values()].index(tag))
        descriptions = {tag: description for tag, description in BEHAVIOR_EPOCHS.values()}
        epochs = TimeIntervals(
            name="epochs",
            description=(
                "behavior epochs of the lab's Analysis/BehavEpochs.mat (CreateEpochs: each epoch is one or more "
                "sub-recordings), tagged: "
                + "; ".join(f"{tag}: {descriptions[tag]}" for tag in present)
                + ("" if not notes else ". Notes: " + "; ".join(notes))
                + "."
                + EPOCH_NOTES.get(self.session_id, "")
            ),
        )
        epochs.add_column(name="lab_epoch", description="name of the lab's intervalSet in BehavEpochs.mat")
        epochs.add_column(name="sub_recordings", description="the sub-recordings (.dat files) the interval overlaps")
        epochs.add_column(
            name="lab_sub_recordings",
            description="the sub-recordings the lab lists for this kind of epoch (its xxxEpIx in BehavEpochs.mat)",
        )
        for start, stop, tag, lab_name, names, lab_names in sorted(rows):
            epochs.add_interval(
                start_time=start,
                stop_time=stop,
                tags=[tag],
                lab_epoch=lab_name,
                sub_recordings=names,
                lab_sub_recordings=lab_names,
            )
        nwbfile.epochs = epochs

    def add_paper_states(self, nwbfile: NWBFile):
        rows = []
        for label, (suffix, _) in PAPER_STATES.items():
            file_path = self.file(f".states.{suffix}")
            if file_path.is_file() and file_path.stat().st_size:
                for start, stop in np.loadtxt(file_path, ndmin=2):
                    rows.append((float(start), float(stop), label))
        if not rows:
            return
        present = [label for label in PAPER_STATES if any(row[2] == label for row in rows)]
        table = TimeIntervals(
            name="sleep_states",
            description=(
                "the paper's brain states, from the lab's .states.SWS, .states.REM and .states.Wake files (seconds); "
                + "; ".join(f"{label}: {PAPER_STATES[label][1]}" for label in present)
                + "."
                + EPOCH_NOTES.get(self.session_id, "")
            ),
        )
        table.add_column(name="label", description="brain state: " + ", ".join(present))
        for start, stop, label in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, label=label)
        get_module(nwbfile, "behavior", "behavior and brain states").add(table)

    def add_buzcode_states(self, nwbfile: NWBFile):
        file_path = self.file(".SleepState.states.mat")
        if not file_path.is_file():
            return
        ints = load_mat(file_path, variable_names=["SleepState"])["SleepState"].ints
        rows = []
        for label in ints._fieldnames:
            for start, stop in np.reshape(np.asarray(getattr(ints, label), dtype=float), (-1, 2)):
                rows.append((float(start), float(stop), label))
        present = sorted({label for _, _, label in rows})
        table = TimeIntervals(
            name="sleep_states_buzcode",
            description=(
                "brain states scored in 2019 with buzcode's SleepScoreMaster (the lab's SleepState.states.mat), "
                "later than the paper, which used its own scoring (sleep_states); these are the states of the earlier "
                "DANDI files. "
                + "; ".join(f"{label}: {BUZCODE_STATES.get(label, 'not described')}" for label in present)
            ),
        )
        table.add_column(name="label", description="brain state: " + ", ".join(present))
        for start, stop, label in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, label=label)
        get_module(nwbfile, "behavior", "behavior and brain states").add(table)

    def add_positions(self, nwbfile: NWBFile):
        general_info = self.general_info()
        note = POSITION_NOTES.get(self.session_id, "")
        whl_file_path = self.file(".whl")
        if whl_file_path.is_file():
            whl, malformed = read_columns(whl_file_path, 4)
            whl[whl == -1] = np.nan  # -1 marks frames without a detected LED
            scale = ""
            if "bin2cms" in general_info:
                scale = f" The lab's camera scale is {float(general_info['bin2cms']):.6g} cm per pixel (GeneralInfo.mat bin2cms)."
            for index, color in enumerate(("red", "blue")):
                nwbfile.add_acquisition(
                    SpatialSeries(
                        name=f"{color}_led_position_pixels",
                        description=(
                            f"position of the {color} LED on the head stage in camera pixels (.whl file, columns "
                            f"{2 * index + 1} and {2 * index + 2}; 640 x 480 camera), NaN where the lab gives -1 "
                            "(LED not detected)." + scale + VIDEO_NOTE + note
                        ),
                        data=whl[:, 2 * index : 2 * index + 2],
                        reference_frame="camera image, in pixels from its corner",
                        unit="pixels",
                        starting_time=0.0,
                        rate=POSITION_RATE,
                    )
                )

        behavior = get_module(nwbfile, "behavior", "behavior and brain states")
        pos_file_path = self.file(".pos")
        if pos_file_path.is_file():
            pos, malformed = read_columns(pos_file_path, 4)
            pos[pos == -1] = np.nan
            malformed_note = ""
            if malformed:
                malformed_note = f" Lines {', '.join(map(str, malformed))} of the .pos file are malformed (not 4 numbers) and are NaN."
            position = Position(name="position")
            for index, color in enumerate(("red", "blue")):
                position.add_spatial_series(
                    SpatialSeries(
                        name=f"{color}_led",
                        description=(
                            f"position of the {color} LED in cm (.pos file, columns {2 * index + 1} and {2 * index + 2}, "
                            "scaled to meters): the .whl positions times the lab's camera scale (bin2cms), smoothed "
                            "and interpolated by the lab; NaN where the lab gives -1 (LED not detected)."
                            + malformed_note
                            + VIDEO_NOTE
                            + note
                        ),
                        data=pos[:, 2 * index : 2 * index + 2],
                        reference_frame="camera image scaled to cm, from its corner",
                        conversion=0.01,
                        starting_time=0.0,
                        rate=POSITION_RATE,
                    )
                )
            behavior.add(position)

        ang_file_path = self.file(".ang")
        if ang_file_path.is_file():
            ang, malformed = read_columns(ang_file_path, 1)
            ang[ang == -1] = np.nan
            offset = ""
            if "angOffset" in general_info:
                ang_offset = float(general_info["angOffset"])
                offset = (
                    f" The lab's LED offset for this session is {ang_offset:.6g} rad (GeneralInfo.mat angOffset, the "
                    "angle between the LED axis and the red-front/blue-rear condition): the head direction is the angle "
                    "of the red-minus-blue LED vector in .pos coordinates minus this offset, modulo 2 pi."
                )
            compass = CompassDirection(name="head_direction")
            compass.add_spatial_series(
                SpatialSeries(
                    name="head_direction",
                    description=(
                        "head direction of the lab's .ang file, in radians from 0 to 2 pi; 0 is heading rightward in "
                        "the frame of the .whl/.pos files; NaN where the lab gives -1 (one of the LEDs not detected)."
                        + offset
                        + VIDEO_NOTE
                        + note
                    ),
                    data=ang[:, 0],
                    reference_frame="0 rad: rightward (increasing x) in the camera image",
                    unit="radians",
                    starting_time=0.0,
                    rate=POSITION_RATE,
                )
            )
            behavior.add(compass)

    def add_down_states(self, nwbfile: NWBFile):
        ecephys = None
        dow_file_path = self.file(".evt.dow")
        if dow_file_path.is_file() and dow_file_path.stat().st_size:
            events = read_events(dow_file_path)
            parsed = events["label"].str.extract(r"^(DOWN|UP) ON (ALL)?(\d+)$")
            if parsed[0].isna().any():
                raise ValueError(f"{dow_file_path.name} has labels other than 'DOWN ON k' / 'UP ON k' / 'DOWN ON ALLn'")
            rows = []
            for (is_global, number), selected in parsed.groupby([parsed[1].fillna(""), parsed[2]]).groups.items():
                pairs = self.pair(
                    events.loc[selected], parsed[0].loc[selected], "DOWN", "UP", is_global + number, dow_file_path.name
                )
                rows += [(start, stop, bool(is_global), int(number)) for start, stop, _ in pairs]
            table = TimeIntervals(
                name="down_states",
                description=(
                    "thalamic down states detected by the lab (.evt.dow file; the same as Analysis/DownStates.mat dwEp "
                    "and globalDw), from the lab's Make_DownStates_Thalamus. On each thalamic shank whose multi-unit "
                    "activity (the .clu cluster 1 spikes plus the cells of the lab's cell list) fires above 40 Hz, a "
                    "down state ('DOWN ON k' to 'UP ON k') is a period when that activity, in 2 ms bins, is below 5% "
                    "of its mean rate, lasting at least 80 ms, with gaps under 15 ms merged, a mean rate below 5% of "
                    "the mean and a duration under 1 s. Global down states ('DOWN ON ALLn' to 'UP ON ALLn') are periods "
                    "when at least n of these shanks are in a down state at once (n = 1 to 5, in 2 ms steps), lasting "
                    "at least 80 ms, with gaps under 15 ms merged; the tables for different n overlap"
                ),
            )
            table.add_column(
                name="shank", description="shank the down state was detected on; -1 for global down states"
            )
            table.add_column(
                name="min_shanks",
                description="for global down states, the minimum number n of shanks in a down state at once; 0 otherwise",
            )
            for start, stop, is_global, number in sorted(rows):
                table.add_row(
                    start_time=start,
                    stop_time=stop,
                    shank=-1 if is_global else number,
                    min_shanks=number if is_global else 0,
                )
            ecephys = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")
            ecephys.add(table)

        hdd_file_path = self.file(".evt.hdD")
        if hdd_file_path.is_file() and hdd_file_path.stat().st_size:
            events = read_events(hdd_file_path)
            parsed = events["label"].str.extract(r"^HD (DOWN|UP) ON$")
            if parsed[0].isna().any():
                raise ValueError(f"{hdd_file_path.name} has labels other than 'HD DOWN ON' and 'HD UP ON'")
            rows = self.pair(events, parsed[0], "DOWN", "UP", "HD", hdd_file_path.name)
            table = TimeIntervals(
                name="hd_down_states",
                description=(
                    "down states of the population of thalamic head-direction cells detected by the lab (.evt.hdD file: "
                    "'HD DOWN ON' to 'HD UP ON'; the same as Analysis/DownStates.mat hdDwEp), from the lab's "
                    "Make_DownStatesHD_Thalamus: periods when the pooled spikes of the thalamic HD cells (is_hd_cell), "
                    "in 2 ms bins, are below 5% of their mean rate, lasting at least 80 ms, with gaps under 15 ms "
                    "merged, a mean rate below 5% of the mean and a duration under 1 s"
                ),
            )
            for start, stop, _ in sorted(rows):
                table.add_row(start_time=start, stop_time=stop)
            ecephys = ecephys or get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")
            ecephys.add(table)

    @staticmethod
    def pair(events, kinds, start_kind: str, stop_kind: str, key: str, file_name: str) -> list:
        """(start, stop, key) of alternating start and stop marks."""
        times = events["time"].to_numpy()
        kinds = kinds.to_numpy()
        order = np.argsort(times, kind="stable")
        times, kinds = times[order], kinds[order]
        if len(times) % 2 or not (np.all(kinds[0::2] == start_kind) and np.all(kinds[1::2] == stop_kind)):
            raise ValueError(f"{file_name}: the {start_kind}/{stop_kind} marks of {key} do not alternate")
        return [(float(start), float(stop), key) for start, stop in zip(times[0::2], times[1::2])]

    def add_ripples(self, nwbfile: NWBFile):
        rip_file_path = self.file(".evt.rip")
        if not rip_file_path.is_file() or not rip_file_path.stat().st_size:
            return
        events = read_events(rip_file_path)
        parsed = events["label"].str.extract(r"^Ripple (start|peak|stop) ?(\d*)$")
        if parsed[0].isna().any():
            raise ValueError(f"{rip_file_path.name} has labels other than 'Ripple start/peak/stop n'")
        marks = {mark: events["time"][parsed[0] == mark].to_numpy() for mark in ("start", "peak", "stop")}
        if not len(marks["start"]) == len(marks["peak"]) == len(marks["stop"]):
            raise ValueError(f"{rip_file_path.name} has unmatched start, peak and stop marks")
        if np.any(marks["start"] > marks["stop"]):
            raise ValueError(f"{rip_file_path.name}: a ripple stops before it starts")
        n_peak_outside = int(np.sum((marks["peak"] < marks["start"]) | (marks["peak"] > marks["stop"])))
        numbers = sorted(set(parsed[1]))
        # .sts.RIPPLES: start, peak, stop (s), peak normalized power and frequency (Hz) of the same ripples
        sts = None
        sts_file_path = self.file(".sts.RIPPLES")
        if sts_file_path.is_file():
            sts = np.loadtxt(sts_file_path, ndmin=2)
            if sts.shape != (len(marks["start"]), 5) or not np.allclose(sts[:, 1], marks["peak"], atol=1e-3):
                sts = None
        general_info = self.general_info()
        channel = ""
        if "channelStructure" in general_info:
            structure = general_info["channelStructure"]
            channels = dict(zip(np.atleast_1d(structure.keys), np.atleast_1d(structure.values)))
            if "hippocampus" in channels:
                channel = (
                    f" on channel {int(np.atleast_1d(channels['hippocampus'])[0])} (GeneralInfo.mat channelStructure)"
                )
        table = TimeIntervals(
            name="ripples",
            description=(
                "hippocampal sharp-wave ripples detected by the lab on a CA1 wire" + channel + " (.evt.rip file: "
                "'Ripple start', 'Ripple peak' and 'Ripple stop', followed by the number "
                + "/".join(numbers)
                + ", the channel argument of the lab's SaveRippleEvents; the same ripples as the .sts.RIPPLES file), "
                "from the lab's FindRipples_Thalamus: the LFP filtered at 80-300 Hz during slow-wave sleep, with an "
                "envelope above 1 s.d. and a peak above 5 s.d. (FMAToolbox FindRipples), excluding events also found "
                "on a noise channel"
                + (
                    ""
                    if not n_peak_outside
                    else f". In {n_peak_outside} ripple(s) the lab's peak lies outside the start-stop interval; kept as given"
                )
            ),
        )
        table.add_column(name="peak_time", description="time of the ripple peak (s)")
        if sts is not None:
            table.add_column(
                name="peak_normalized_power",
                description="peak power of the filtered LFP in s.d. (column 4 of the .sts.RIPPLES file)",
            )
            table.add_column(name="frequency", description="ripple frequency in Hz (column 5 of the .sts.RIPPLES file)")
        order = np.argsort(marks["start"], kind="stable")
        for index in order:
            row = dict(
                start_time=float(marks["start"][index]),
                stop_time=float(marks["stop"][index]),
                peak_time=float(marks["peak"][index]),
            )
            if sts is not None:
                row.update(peak_normalized_power=float(sts[index, 3]), frequency=float(sts[index, 4]))
            table.add_row(**row)
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(table)
