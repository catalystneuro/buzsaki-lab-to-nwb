"""Epochs, position, laps, sleep states, lab events and videos of a Girardeau session (DANDI:000061)."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.behavior import Position, SpatialSeries
from pynwb.epoch import TimeIntervals
from pynwb.event import EventsTable
from pynwb.image import ImageSeries

from .girardeauutils import WHL_RATE, load_mat, read_evt

EPOCH_DESCRIPTIONS = {
    "prerun": "running on the linear track before training, with water rewards at both ends and no air puff",
    "presleep": "rest and sleep in the home cage before training",
    "run": (
        "training on the linear track: water rewards at both ends and an air puff at a fixed place on the track, in one "
        "running direction only"
    ),
    "postsleep": "rest and sleep in the home cage after training",
    "postrun": "running on the linear track after training, with water rewards and no air puff",
}
EPOCH_NOTE = "a label of the lab's .cat.evt file that the paper does not describe"
DIRECTIONS = {"LtoRlaps": "left to right", "RtoLlaps": "right to left", "Uturnlaps": "U-turn"}
STATE_FILES_NOTE = (
    "scored by the lab in whole seconds (the session's -States.mat; the lab's States.mat holds the same intervals)"
)


def read_intervals(value) -> np.ndarray:
    """(n, 2) intervals from a .mat value that may be empty or a single interval."""
    array = np.asarray(value, dtype=float)
    if array.size == 0:
        return np.zeros((0, 2))
    return array.reshape(-1, 2)


class GirardeauBehaviorInterface(BaseDataInterface):
    """Behavior and brain states of a session, from the lab's files in the session folder."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def file(self, suffix: str) -> Path:
        return self.session_path / f"{self.session_id}{suffix}"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        self.add_epochs(nwbfile)
        self.add_position(nwbfile)
        self.add_laps(nwbfile)
        self.add_running_bouts(nwbfile)
        self.add_sleep_states(nwbfile)
        self.add_oscillation_events(nwbfile)
        self.add_task_events(nwbfile)
        self.add_videos(nwbfile)

    def read_epochs(self) -> list:
        """(name, start, stop) in seconds; the .cat.evt times are in ms."""
        lines = [line.split(maxsplit=1) for line in self.file(".cat.evt").read_text().splitlines() if line.strip()]
        epochs = []
        for (start, start_text), (stop, stop_text) in zip(lines[::2], lines[1::2]):
            name = start_text.removeprefix("beginning of ")
            if stop_text != f"end of {name}":
                raise ValueError(f"{self.session_id}: unmatched .cat.evt lines '{start_text}' and '{stop_text}'")
            epochs.append((name, float(start) / 1000, float(stop) / 1000))
        return epochs

    def add_epochs(self, nwbfile: NWBFile):
        self.epochs = self.read_epochs()
        labels = [name.removeprefix(f"{self.session_id}-").split("-", 1)[-1] for name, _, _ in self.epochs]
        nwbfile.epochs = TimeIntervals(
            name="epochs",
            description=(
                "the sub-recordings concatenated into the session, from the lab's .cat.evt file (times in ms there, in "
                "seconds here); tags are the epoch labels of the file names"
            ),
        )
        nwbfile.add_epoch_column(
            name="epoch_name", description="name of the epoch's sub-recording in the .cat.evt file"
        )
        nwbfile.add_epoch_column(
            name="behavior", description="what the rat did during the epoch, as described in the paper"
        )
        for (name, start, stop), label in zip(self.epochs, labels):
            nwbfile.add_epoch(
                start_time=start,
                stop_time=stop,
                tags=[label],
                epoch_name=name,
                behavior=EPOCH_DESCRIPTIONS.get(label, EPOCH_NOTE),
            )

    def epoch_of(self, time: float) -> str:
        for name, start, stop in self.epochs:
            if start <= time < stop:
                return name.removeprefix(f"{self.session_id}-").split("-", 1)[-1]
        return "none"

    def add_position(self, nwbfile: NWBFile):
        if not self.file(".whl").is_file():
            return
        # Columns separated by spaces, or by commas (Rat08-20130720)
        whl = pd.read_csv(self.file(".whl"), sep=r"[\s,]+", header=None, engine="python")
        whl = whl.to_numpy(dtype=float, copy=True)
        whl[whl < 0] = np.nan  # -1 marks samples without a detected LED
        position = Position(name="position")
        for index in range(whl.shape[1] // 2):
            position.add_spatial_series(
                SpatialSeries(
                    name=f"led{index + 1}",
                    description=(
                        f"position of head-stage LED {index + 1} in camera pixels (columns {2 * index + 1} and "
                        f"{2 * index + 2} of the session's .whl file: x, y), sampled by the lab at 1250/32 Hz on the "
                        "session clock (the .whl files of the epochs, in order, make up this file); NaN where the LED "
                        "was not detected. The pixel size is not given in the source."
                    ),
                    data=whl[:, 2 * index : 2 * index + 2],
                    reference_frame="camera image, origin at the top left corner, in pixels",
                    unit="pixels",
                    starting_time=0.0,
                    rate=WHL_RATE,
                )
            )
        get_module(nwbfile, "behavior", "behavior and sleep states").add(position)

    def add_laps(self, nwbfile: NWBFile):
        laps_file = next(iter(sorted(self.session_path.glob("*-Laps.mat"))), None)
        if laps_file is None:
            return
        laps = load_mat(laps_file)
        lap_types = {}
        type_file = self.file("-LapType.mat")
        if type_file.is_file():
            types = load_mat(type_file)
            for variable, lap_type in (("aplaps", "air-puff direction"), ("safelaps", "safe direction")):
                for start, stop in read_intervals(types[variable].all):
                    lap_types[(round(start, 4), round(stop, 4))] = lap_type
        rows = []
        for variable, direction in DIRECTIONS.items():
            for start, stop in read_intervals(laps.get(variable, [])):
                lap_type = lap_types.pop((round(start, 4), round(stop, 4)), "not classified")
                rows.append((start, stop, direction, lap_type))
        if lap_types:
            raise ValueError(f"{self.session_id}: laps of -LapType.mat missing from {laps_file.name}: {lap_types}")
        nwbfile.trials = TimeIntervals(
            name="trials",
            description=(
                "laps on the linear track, from the lab's lap detection on the LED position (the -Laps.mat and -LapType.mat "
                "files), in seconds"
            ),
        )
        nwbfile.add_trial_column(
            name="direction",
            description=(
                f"running direction of the lap ({laps_file.name}: LtoRlaps, RtoLlaps and Uturnlaps); left and "
                "right are the ends of the track in the camera image: left-to-right laps go from low to high x of "
                "the LED position (checked in Rat08-20130710); a U-turn lap is probably a run that turned back before "
                f"the other end. The file's leftLimit and rightLimit ({int(laps['leftLimit'])} and "
                f"{int(laps['rightLimit'])}) are not documented and do not match the pixel x of the track ends"
            ),
        )
        nwbfile.add_trial_column(
            name="lap_type",
            description=(
                "the lab's lap type (-LapType.mat): 'air-puff direction' (aplaps), laps in the running direction in "
                "which the air puff was delivered during the run epoch, also in the pre- and post-run epochs when no "
                "puff was given; 'safe direction' (safelaps), laps in the other direction; 'not classified' for laps "
                "not in that file (U-turns)"
            ),
        )
        nwbfile.add_trial_column(name="epoch", description="label of the epoch the lap starts in")
        for start, stop, direction, lap_type in sorted(rows):
            nwbfile.add_trial(
                start_time=float(start),
                stop_time=float(stop),
                direction=direction,
                lap_type=lap_type,
                epoch=self.epoch_of(start),
            )

    def add_running_bouts(self, nwbfile: NWBFile):
        if not self.file("-TrackRunTimes.mat").is_file():
            return
        bouts = read_intervals(load_mat(self.file("-TrackRunTimes.mat"))["trackruntimes"])
        table = TimeIntervals(
            name="running_bouts",
            description=(
                "running bouts on the linear track in the track epochs, from the lab's -TrackRunTimes.mat "
                "(trackruntimes), in seconds. These are not laps (see the trials table); the earlier DANDI files "
                "stored them as 'trials'. How the lab detected them is not documented."
            ),
        )
        table.add_column(name="epoch", description="label of the epoch the bout starts in")
        for start, stop in bouts:
            table.add_row(start_time=float(start), stop_time=float(stop), epoch=self.epoch_of(start))
        nwbfile.add_time_intervals(table)

    def add_sleep_states(self, nwbfile: NWBFile):
        behavior = get_module(nwbfile, "behavior", "behavior and sleep states")
        if self.file("-States.mat").is_file():
            states = load_mat(self.file("-States.mat"))
            rows = [
                (float(start), float(stop), label)
                for label in ("wake", "drowsy", "sws", "Rem")
                for start, stop in read_intervals(states.get(label, []))
            ]
            table = TimeIntervals(
                name="sleep_states",
                description=(
                    f"brain states {STATE_FILES_NOTE}, with the lab's labels unchanged: wake, drowsy, sws (slow-wave "
                    "or non-REM sleep) and Rem (REM sleep)"
                ),
            )
            table.add_column(name="label", description="the lab's state label: wake, drowsy, sws or Rem")
            for start, stop, label in sorted(rows):
                table.add_row(start_time=start, stop_time=stop, label=label)
            behavior.add(table)
        if self.file(".SleepState.states.mat").is_file():
            sleep_state = load_mat(self.file(".SleepState.states.mat"))["SleepState"]
            detector = sleep_state.detectorinfo
            rows = [
                (float(start), float(stop), label)
                for label in sleep_state.ints._fieldnames
                for start, stop in read_intervals(getattr(sleep_state.ints, label))
            ]
            table = TimeIntervals(
                name="sleep_states_buzcode",
                description=(
                    f"brain states scored in {str(detector.detectiondate)} by the lab's buzcode {detector.detectorname} "
                    "(SleepState.states.mat), after the paper; the earlier DANDI files used these. The paper's states "
                    "are in sleep_states."
                ),
            )
            table.add_column(name="label", description="buzcode state: WAKEstate, NREMstate or REMstate")
            for start, stop, label in sorted(rows):
                table.add_row(start_time=start, stop_time=stop, label=label)
            behavior.add(table)

    def add_oscillation_events(self, nwbfile: NWBFile):
        """Ripples (.rip.evt) and beta events (.bet.evt): start, peak and stop lines with a number."""
        for suffix, name, word, description in (
            (
                ".rip.evt",
                "ripples",
                "Ripple",
                "hippocampal sharp-wave ripples detected by the lab (.rip.evt)",
            ),
            (
                ".bet.evt",
                "beta_events",
                "Beta",
                "beta-band events detected by the lab (.bet.evt); the paper does not describe their detection",
            ),
        ):
            if not self.file(suffix).is_file() or self.file(suffix).stat().st_size == 0:
                continue
            events = read_evt(self.file(suffix))
            parsed = events.text.str.extract(rf"^{word} (?P<mark>start|peak|stop) (?P<number>\d+)$")
            if parsed.mark.isna().any():
                raise ValueError(f"{self.file(suffix).name} has unexpected lines")
            starts, stops = (events[parsed.mark == mark] for mark in ("start", "stop"))
            peaks = events[parsed.mark == "peak"]
            if len(starts) != len(stops) or (len(peaks) and len(peaks) != len(starts)):
                raise ValueError(f"{self.file(suffix).name} has unmatched start, peak and stop lines")
            numbers = parsed.number[parsed.mark == "start"].astype(int).to_numpy()
            table = TimeIntervals(
                name=name,
                description=(
                    f"{description}, in seconds (ms in the file). Each line of the file is '{word} start|peak|stop N'; "
                    "N is kept in the channel column."
                ),
            )
            if len(peaks):
                table.add_column(name="peak_time", description="time of the event's peak (s)")
            table.add_column(
                name="channel",
                description=(
                    f"the number N of the file's labels ('{word} start N'), probably the channel the events were "
                    "detected on (not documented)"
                ),
            )
            rows = zip(starts.ms.to_numpy() / 1000, stops.ms.to_numpy() / 1000, numbers)
            for index, (start, stop, number) in enumerate(rows):
                row = dict(start_time=float(start), stop_time=float(stop), channel=int(number))
                if len(peaks):
                    row["peak_time"] = float(peaks.ms.to_numpy()[index] / 1000)
                table.add_row(**row)
            get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(table)

    def add_task_events(self, nwbfile: NWBFile):
        """Water rewards (.lrw.evt, .rrw.evt) and air puffs (.puf.evt), as events tables."""
        rewards = []
        for suffix, side in ((".lrw.evt", "left"), (".rrw.evt", "right")):
            if self.file(suffix).is_file() and self.file(suffix).stat().st_size:
                rewards += [(float(ms) / 1000, side) for ms in read_evt(self.file(suffix)).ms]
        if rewards:
            table = EventsTable(
                name="rewards",
                description=(
                    "water rewards at the ends of the linear track (the lab's .lrw.evt and .rrw.evt files, times in ms "
                    "there, in seconds here)"
                ),
                source_description="the lab's event files, probably from the reward valve inputs of the recording system",
            )
            table.add_column(name="side", description="end of the track: left (.lrw.evt) or right (.rrw.evt)")
            for timestamp, side in sorted(rewards):
                table.add_event(timestamp=timestamp, side=side)
            nwbfile.add_events_table(table)
        if self.file(".puf.evt").is_file() and self.file(".puf.evt").stat().st_size:
            times = sorted(float(ms) / 1000 for ms in read_evt(self.file(".puf.evt")).ms)
            table = EventsTable(
                name="air_puffs",
                description=(
                    "air puffs delivered at a fixed place on the linear track, in one running direction, during the run "
                    "epoch (the lab's .puf.evt file, times in ms there, in seconds here)"
                ),
                source_description="the lab's event file, probably from the air-puff input of the recording system",
            )
            for timestamp in times:
                table.add_event(timestamp=timestamp)
            nwbfile.add_events_table(table)

    def add_videos(self, nwbfile: NWBFile):
        """The epochs' .mpg files that are in the session folder, as external files with approximate frame times."""
        for name, start, stop in self.epochs:
            video_file_path = self.session_path / f"{name}.mpg"
            if not video_file_path.is_file():
                continue
            tsp_file_path = self.session_path / f"{name}.tsp"
            if not tsp_file_path.is_file():
                continue
            n_frames = sum(1 for _ in open(tsp_file_path))
            label = name.removeprefix(f"{self.session_id}-")
            nwbfile.add_acquisition(
                ImageSeries(
                    name=f"video_{label.replace('-', '_')}",
                    description=(
                        f"video of the {label} epoch from the camera (Basler acA1300-200uc, the lab's "
                        f"session.mat), in the external file {video_file_path.name}. The frame times were not recorded "
                        "(the time column of the .tsp file is -2147483648 on every line). The frame times here are "
                        f"APPROXIMATE: the {n_frames} frames (lines of {tsp_file_path.name}, the LED tracking of each "
                        "frame) are spread evenly over the epoch from its start, so the rate is the mean frame rate "
                        "of the epoch, not a measured one."
                    ),
                    external_file=[video_file_path.name],
                    format="external",
                    starting_frame=[0],
                    starting_time=start,
                    rate=n_frames / (stop - start),
                    num_samples=n_frames,
                    unit="n.a.",
                )
            )
