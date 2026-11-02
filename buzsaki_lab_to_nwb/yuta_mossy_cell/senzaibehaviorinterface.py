"""Behavior, brain states and events of a Senzai session (DANDI:000003)."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile, TimeSeries
from pynwb.misc import AnnotationSeries
from pynwb.behavior import Position, SpatialSeries
from pynwb.epoch import TimeIntervals
from scipy.io import loadmat

STATE_DESCRIPTIONS = {
    "awake": "wake, scored from the theta/delta ratio of the hilus LFP and the movement of the mouse",
    "nrem": "non-REM sleep, scored from the theta/delta ratio of the hilus LFP and the movement of the mouse",
    "rem": "REM sleep, scored from the theta/delta ratio of the hilus LFP and the movement of the mouse",
    "quiet": "a label of the lab's state scoring that the paper does not define",
    "transit": "a label of the lab's state scoring that the paper does not define",
}
# The circular T-maze: side arms are semicircles of 102 cm, so the circle has a radius of 32.5 cm and the 65 cm central
# arm is its diameter. One normalized unit of the lab's position files is the radius.
METERS_PER_MAZE_UNIT = 0.325
TRIAL_COLUMNS = {
    "left_run": "the mouse ran to the left side arm",
    "right_run": "the mouse ran to the right side arm",
    "error_run": "the lab's error_run flag (the task rewards alternating between the side arms)",
    "stim_run": "light was delivered during the run",
    "both_visit": "the lab's both_visit flag",
    "arm_start": "time the mouse entered the central arm (s)",
    "arm_end": "time the mouse left the central arm (s)",
    "sens_pass": "time the mouse passed the sensor at the end of the central arm (s)",
    "light_start": "start of light delivery during the run (s); 0 if none",
    "light_end": "end of light delivery during the run (s); 0 if none",
    "sessionIdx": "the lab's sessionIdx of the run",
}
# Column names of EightMazeRun.mat, as given by the EightMazeRunInfo.mat files
RUN_COLUMNS = [
    "run_start",
    "run_end",
    "left_run",
    "right_run",
    "error_run",
    "stim_run",
    "both_visit",
    "arm_start",
    "arm_end",
    "sens_pass",
    "light_start",
    "light_end",
    "sessionIdx",
]
PULSE_NAME = re.compile(r"PulseStim_(?P<voltage>[\d.]+)V_(?P<duration>\d+)ms_LD(?P<diodes>\d+)")


def find_discontinuities(times: np.ndarray, factor: float = 10000) -> np.ndarray:
    """(start, stop) of the stretches of a time series separated by gaps much longer than its median step."""
    steps = np.diff(times)
    breaks = np.flatnonzero(steps > np.median(steps) * factor)
    starts = np.concatenate([[0], breaks + 1])
    stops = np.concatenate([breaks, [len(times) - 1]])
    return np.column_stack([times[starts], times[stops]])


class SenzaiBehaviorInterface(BaseDataInterface):
    """Brain states, LED positions, T-maze position and trials, dentate spikes and light pulses of a session."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def file(self, suffix: str) -> Path:
        return self.session_path / f"{self.session_id}{suffix}"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        self.epochs = []
        self.add_states(nwbfile)
        self.add_led_positions(nwbfile)
        self.add_maze(nwbfile)
        self.add_open_fields(nwbfile)
        for epoch in sorted(self.epochs, key=lambda epoch: epoch["start_time"]):
            nwbfile.add_epoch(**epoch)
        self.add_dentate_spikes(nwbfile)
        self.add_light_pulses(nwbfile)
        self.add_lab_events(nwbfile)

    def add_states(self, nwbfile: NWBFile):
        if not self.file("--StatePeriod.mat").is_file():
            return
        periods = loadmat(str(self.file("--StatePeriod.mat")), squeeze_me=True, struct_as_record=False)["StatePeriod"]
        rows = []
        for label in periods._fieldnames:
            for start, stop in np.reshape(getattr(periods, label), (-1, 2)):
                rows.append((float(start), float(stop), label))
        present = sorted({label for _, _, label in rows})
        table = TimeIntervals(
            name="brain_states",
            description=(
                "brain states from the lab's StatePeriod.mat, in whole seconds; "
                + "; ".join(f"{label}: {STATE_DESCRIPTIONS.get(label, 'not described')}" for label in present)
            ),
        )
        table.add_column(name="label", description="brain state: " + ", ".join(present))
        for start, stop, label in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, label=label)
        get_module(nwbfile, "behavior", "behavior and brain states").add(table)

    def add_led_positions(self, nwbfile: NWBFile):
        if not self.file(".whl").is_file():
            return
        whl = pd.read_csv(self.file(".whl"), sep=r"\s+", header=None).to_numpy(dtype=float, copy=True)
        whl[whl < 0] = np.nan  # -1 marks frames without a detected LED
        for index in range(whl.shape[1] // 2):
            nwbfile.add_acquisition(
                SpatialSeries(
                    name=f"led{index}_position",
                    description=f"position of LED {index} on the head stage in camera pixels (.whl file), NaN when not detected",
                    data=whl[:, 2 * index : 2 * index + 2],
                    reference_frame="camera image",
                    unit="pixels",
                    rate=1250 / 32,
                )
            )

    def add_maze(self, nwbfile: NWBFile):
        position_file = self.file("__EightMazePosition.mat")
        if not position_file.is_file():
            return
        mat = loadmat(str(position_file), squeeze_me=True)
        behavior = get_module(nwbfile, "behavior", "behavior and brain states")
        norm = mat["twhl_norm"]
        times = norm[:, 0]
        position = Position(name="t_maze_position")
        position.add_spatial_series(
            SpatialSeries(
                name="position",
                description=(
                    "head position on the circular T-maze (twhl_norm), in the lab's normalized maze coordinates scaled "
                    "to meters: one unit is the 32.5 cm radius of the circle formed by the side arms"
                ),
                data=norm[:, 1:],
                timestamps=times,
                reference_frame="center of the circle formed by the side arms",
                conversion=METERS_PER_MAZE_UNIT,
            )
        )
        if "twhl_linearized" in mat:
            linear = mat["twhl_linearized"]
            position.add_spatial_series(
                SpatialSeries(
                    name="central_arm_position",
                    description=(
                        "position along the 65 cm central arm (column 1 of twhl_linearized, 0 to 2 normalized units "
                        "scaled to meters); 0 while the mouse is on a side arm"
                    ),
                    data=linear[:, 1],
                    timestamps=times,
                    reference_frame="start of the central arm",
                    conversion=METERS_PER_MAZE_UNIT,
                )
            )
            behavior.add(
                TimeSeries(
                    name="side_arm_angle",
                    description=(
                        "angle along the circular side arms (column 2 of twhl_linearized); positive on runs the lab "
                        "marks as left runs and negative on right runs, 0 while the mouse is on the central arm"
                    ),
                    data=linear[:, 2],
                    timestamps=times,
                    unit="radians",
                )
            )
        behavior.add(position)

        epochs = find_discontinuities(times)
        for index, (start, stop) in enumerate(epochs):
            self.epochs.append(dict(start_time=float(start), stop_time=float(stop), tags=[f"t_maze_{index}"]))

        run_file = self.file("__EightMazeRun.mat")
        if run_file.is_file():
            runs = np.atleast_2d(loadmat(str(run_file), squeeze_me=True)["EightMazeRun"])
            info_file = self.file("__EightMazeRunInfo.mat")
            if info_file.is_file():
                info = list(loadmat(str(info_file), squeeze_me=True)["EightMazeRunInfo"])
            elif runs.shape[1] == len(RUN_COLUMNS):
                # Some sessions lack the column names; their runs have the same 13 columns as the others
                info = RUN_COLUMNS
            else:
                raise ValueError(f"{run_file.name} has {runs.shape[1]} columns and no EightMazeRunInfo.mat")
            columns = [name for name in info if name in TRIAL_COLUMNS]
            for name in columns:
                nwbfile.add_trial_column(name=name, description=TRIAL_COLUMNS[name])
            for run in runs:
                values = dict(zip(info, run))
                nwbfile.add_trial(
                    start_time=float(values["run_start"]),
                    stop_time=float(values["run_end"]),
                    **{
                        name: bool(values[name]) if name.endswith(("_run", "_visit")) else float(values[name])
                        for name in columns
                    },
                )

    def add_open_fields(self, nwbfile: NWBFile):
        """Head position in the open field sessions (__OpenFieldPosition_<label>.mat), one series per session."""
        files = sorted(self.session_path.glob(f"{self.session_id}__OpenFieldPosition_*.mat"))
        if not files:
            return
        position = Position(name="open_field_position")
        for position_file in files:
            label = position_file.stem.split("__OpenFieldPosition_")[1]
            norm = loadmat(str(position_file), squeeze_me=True)["twhl_norm"]
            times = norm[:, 0]
            if label == "ExtraLarge":
                description = (
                    f"head position in the lab's '{label}' open field session, with each axis normalized to 0-1 across "
                    "the arena; the size of this arena is not given in the paper, so the values are not scaled"
                )
                conversion, unit = 1.0, "normalized arena units"
            else:
                description = (
                    f"head position in the lab's '{label}' open field session (twhl_norm), scaled to meters: each "
                    "axis is normalized to 0-1 across the 46 x 46 cm arena. The paper's mice explored open fields A, "
                    "B and A' and the same arenas in another room or behind a curtain; the session labels are the lab's"
                )
                conversion, unit = 0.46, "meters"
            position.add_spatial_series(
                SpatialSeries(
                    name=label,
                    description=description,
                    data=norm[:, 1:],
                    timestamps=times,
                    reference_frame="corner of the arena where both normalized coordinates are 0",
                    conversion=conversion,
                    unit=unit,
                )
            )
            self.epochs.append(
                dict(start_time=float(times[0]), stop_time=float(times[-1]), tags=[f"open_field_{label}"])
            )
        get_module(nwbfile, "behavior", "behavior and brain states").add(position)

    def add_dentate_spikes(self, nwbfile: NWBFile):
        files = sorted(self.session_path.glob(f"{self.session_id}.DS[12].ch*.evt"))
        if not files:
            return
        table = TimeIntervals(
            name="dentate_spikes",
            description=(
                "dentate spikes detected by the lab (.DS1.ch*.evt and .DS2.ch*.evt files); DS2 events are periods when "
                "the 2-50 Hz LFP difference between a hilus and a molecular layer site exceeded 1.14 mV"
            ),
        )
        table.add_column(name="type", description="DS1 or DS2")
        table.add_column(name="peak_time", description="time of the dentate spike peak (s)")
        table.add_column(name="hilus_channel", description="channel the dentate spike was detected on")
        rows = []
        for evt_file in files:
            kind, channel = re.search(r"\.(DS[12])\.ch(\d+)\.evt$", evt_file.name).groups()
            events = pd.read_csv(evt_file, sep="\t", header=None, names=["ms", "label"])
            marks = events.label.str.extract(r"(start|peak|stop)")[0]
            starts, peaks, stops = (events.ms[marks == mark].to_numpy() / 1000 for mark in ("start", "peak", "stop"))
            if not len(starts) == len(peaks) == len(stops):
                raise ValueError(f"{evt_file.name} has unmatched start, peak and stop marks")
            rows += [(start, stop, kind, peak, int(channel)) for start, peak, stop in zip(starts, peaks, stops)]
        for start, stop, kind, peak, channel in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, type=kind, peak_time=peak, hilus_channel=channel)
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(table)

    def add_light_pulses(self, nwbfile: NWBFile):
        """Light pulse files whose names give the voltage, duration and laser diodes; other .evt files go to
        add_lab_events."""
        files = [
            path for path in sorted(self.session_path.glob(f"{self.session_id}.*.evt")) if PULSE_NAME.search(path.name)
        ]
        rows, notes = [], []
        for evt_file in files:
            match = PULSE_NAME.search(evt_file.name)
            onsets = pd.read_csv(evt_file, sep="\t", header=None, usecols=[0]).iloc[:, 0].to_numpy() / 1000
            unique_onsets = np.unique(onsets)  # sorted
            if len(unique_onsets) < len(onsets):
                notes.append(f"{evt_file.name} lists {len(onsets) - len(unique_onsets)} onsets twice")
            duration = float(match["duration"]) / 1000
            rows += [
                (onset, onset + duration, float(match["voltage"]), match["diodes"], match[0]) for onset in unique_onsets
            ]
        if not rows:
            return
        table = TimeIntervals(
            name="light_pulses",
            description=(
                "light pulses delivered through the optical fibers on the probe (.PulseStim_<voltage>V_<duration>ms_"
                "LD<diodes>.evt files), with the voltage, pulse duration and laser diodes taken from each file's name; "
                "each onset is kept once" + ("" if not notes else " (" + "; ".join(notes) + ")")
            ),
        )
        table.add_column(name="voltage", description="voltage driving the laser diode (V)")
        table.add_column(name="laser_diodes", description="laser diode code from the file name (e.g. 1, 2 or 12)")
        table.add_column(name="protocol", description="name of the lab's event file")
        for start, stop, voltage, diodes, protocol in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, voltage=voltage, laser_diodes=diodes, protocol=protocol)
        nwbfile.add_time_intervals(table)

    def add_lab_events(self, nwbfile: NWBFile):
        """Every other .evt file, as instants: stimulation and ripple events whose file names do not give a duration."""
        files = [
            path
            for path in sorted(self.session_path.glob(f"{self.session_id}.*.evt"))
            if not PULSE_NAME.search(path.name) and not re.search(r"\.DS[12]\.ch\d+\.evt$", path.name)
        ]
        if not files:
            return
        module = get_module(nwbfile, "events", "events from the lab's .evt files that are instants")
        for evt_file in files:
            label = evt_file.name[len(self.session_id) + 1 : -len(".evt")]
            events = pd.read_csv(evt_file, sep="\t", header=None, names=["ms", "text"], dtype={"text": str})
            events = events.fillna("").drop_duplicates().sort_values("ms")
            module.add(
                AnnotationSeries(
                    name=label,
                    description=f"events of the lab's {evt_file.name} file, with the text of each line; repeated lines are kept once",
                    data=events.text.astype(str).to_numpy(),
                    timestamps=events.ms.to_numpy(dtype=float) / 1000,
                )
            )
