"""Epochs, sleep states, position and laps of a Grosmark session (DANDI:000044)."""

from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile
from pynwb.behavior import Position, SpatialSeries
from pynwb.epoch import TimeIntervals
from scipy.io import loadmat

from .grosmarkutils import MAZE_DESCRIPTIONS, read_sess_info

EPOCHS = {
    "PREEpoch": ("PRE", "long rest/sleep recording in the home cage, in a familiar room"),
    "MazeEpoch": ("MAZE", "running on a novel maze in a novel room, for water reward"),
    "POSTEpoch": ("POST", "long rest/sleep recording in the home cage, back in the familiar room"),
}
# Gatsby_08022013: the lab's sessInfo gives POST = [19414.3, 30413.628] s and sessDuration = 30413.628 s, as does the
# lab's recording summary, but its .eeg file, spikes and state scorings run to 32,002.4 s
EPOCH_NOTES = {
    "Gatsby_08022013": (
        " In this session the lab's POST epoch ends at 30,413.6 s (sessInfo.Epochs and the lab's recording summary), "
        "but the recording continues to 32,002.4 s: the .eeg file, 263,976 spikes and the lab's own state scoring run "
        "past 30,413.6 s. Whether POST really ends at 30,413.6 s is an open question for the lab; the lab's value is "
        "kept."
    ),
}

# The lab's scoring with TheStateEditor (sessInfo.Epochs), as described in the CRCNS hc-11 data description
LAB_STATES = {
    "Wake": "active waking: high theta/delta ratio and active movement/EMG activity",
    "Drowsy": (
        "drowsy wake/light sleep: low overall spectral power and low movement/EMG activity; often seen at the "
        "wake-NREM transition, within NREM epochs and at the REM-NREM transition"
    ),
    "NREM": "non-REM sleep: high delta/theta ratio and very low movement/EMG activity",
    "Intermediate": (
        "intermediate sleep: short (~30 s) states at the NREM to REM transition with highly elevated pyramidal layer "
        "spindle (12-20 Hz) power and low movement/EMG activity; the lab describes it as a sub-type of NREM sleep "
        "around the NREM to REM transition"
    ),
    "REM": "REM sleep: high theta/delta ratio and very low movement/EMG activity, after NREM episodes",
}
BUZCODE_STATES = {
    "WAKE": "wake, from buzcode's automatic SleepScoreMaster",
    "NREM": "non-REM sleep, from buzcode's automatic SleepScoreMaster",
    "REM": "REM sleep, from buzcode's automatic SleepScoreMaster",
}
SPEED_THRESHOLD = 0.05  # m/s, for the running direction on the circular maze


def timing(times: np.ndarray) -> dict:
    """starting_time and rate for evenly spaced times, otherwise the timestamps."""
    rate = (len(times) - 1) / (times[-1] - times[0])
    if np.max(np.abs(times[0] + np.arange(len(times)) / rate - times)) < 1e-4:
        return dict(starting_time=float(times[0]), rate=float(rate))
    return dict(timestamps=times)


def running_direction(times: np.ndarray, linear: np.ndarray) -> tuple:
    """Fractions of moving samples going toward lower and higher linearized position, wrap-around steps left out."""
    step = np.diff(linear)
    speed = step / np.diff(times)
    valid = np.isfinite(step) & (np.abs(step) < 1.0) & (np.abs(speed) > SPEED_THRESHOLD)
    n = np.isfinite(step).sum()
    return float(np.sum(valid & (step < 0)) / n), float(np.sum(valid & (step > 0)) / n)


class GrosmarkBehaviorInterface(BaseDataInterface):
    """PRE/MAZE/POST epochs, both sleep scorings, position on the maze and laps on the linear tracks.

    The epochs, the lab's 5-state scoring and the position come from the lab's <session>_sessInfo.mat (the CRCNS hc-11
    file); the 3-state scoring from buzcode's <session>.SleepState.states.mat (2019); the laps from position_info.mat.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        laps_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        super().__init__(folder_path=folder_path, laps_file_path=laps_file_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        sess_info = read_sess_info(self.session_path / f"{self.session_id}_sessInfo.mat")
        self.add_epochs(nwbfile, sess_info)
        self.add_lab_states(nwbfile, sess_info)
        self.add_buzcode_states(nwbfile)
        self.add_position(nwbfile, sess_info)
        self.add_laps(nwbfile, sess_info)

    def add_epochs(self, nwbfile: NWBFile, sess_info: dict):
        epochs = sess_info["epochs"]
        nwbfile.epochs = TimeIntervals(
            name="epochs",
            description=(
                "the PRE, MAZE and POST epochs of the session (the lab's sessInfo.Epochs), recorded separately and "
                "concatenated by the lab, so the times are seconds into the concatenated recording."
                + EPOCH_NOTES.get(self.session_id, "")
            ),
        )
        nwbfile.add_epoch_column(name="label", description="epoch: PRE, MAZE or POST")
        nwbfile.add_epoch_column(name="epoch_description", description="what the rat did in the epoch")
        for key, (label, description) in EPOCHS.items():
            start, stop = np.ravel(epochs[key])
            nwbfile.add_epoch(
                start_time=float(start), stop_time=float(stop), label=label, epoch_description=description
            )

    def add_lab_states(self, nwbfile: NWBFile, sess_info: dict):
        rows = [
            (float(start), float(stop), label)
            for label in LAB_STATES
            for start, stop in np.reshape(sess_info["epochs"].get(label, np.empty((0, 2))), (-1, 2))
        ]
        if not rows:
            return
        n_empty = sum(stop <= start for start, stop, _ in rows)
        empty_note = (
            f" {n_empty} bout(s) of the lab's scoring start and end at the same time; they are kept as in the source."
            if n_empty
            else ""
        )
        table = TimeIntervals(
            name="sleep_states",
            description=(
                "the lab's 5-state scoring of the session, made by Andres Grosmark with TheStateEditor from the "
                "pyramidal-layer LFP wavelet spectrum (in particular the theta (5-10 Hz) to delta (1-4 Hz) ratio) and "
                "movement (EMG, accelerometer or position tracking); from sessInfo.Epochs, as documented in the CRCNS "
                "hc-11 data description, the release of the paper's data. "
                + "; ".join(f"{label}: {description}" for label, description in LAB_STATES.items())
                + "."
                + empty_note
            ),
        )
        table.add_column(name="label", description="state: " + ", ".join(LAB_STATES))
        for start, stop, label in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, label=label)
        get_module(nwbfile, "behavior", "behavior and brain states").add(table)

    def add_buzcode_states(self, nwbfile: NWBFile):
        file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"
        if not file_path.is_file():
            return
        sleep_state = loadmat(str(file_path), simplify_cells=True)["SleepState"]
        rows = []
        for name, intervals in sleep_state["ints"].items():
            label = name.removesuffix("state")
            if label not in BUZCODE_STATES:
                raise ValueError(f"Unexpected state {name} in {file_path.name}")
            rows += [(float(start), float(stop), label) for start, stop in np.reshape(intervals, (-1, 2))]
        detector = sleep_state.get("detectorinfo", {})
        table = TimeIntervals(
            name="sleep_states_buzcode",
            description=(
                "a later 3-state scoring (WAKE, NREM, REM) made in 2019 with buzcode's automatic SleepScoreMaster "
                f"(SleepState.states.mat, detection date {detector.get('detectiondate', 'not given')}), from the "
                "slow-wave spectrum and theta ratio of the LFP and the EMG estimated from the LFP. It is not the "
                "scoring of the paper, which is in sleep_states. These were the states of the earlier DANDI files."
            ),
        )
        table.add_column(name="label", description="state: " + ", ".join(BUZCODE_STATES))
        for start, stop, label in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, label=label)
        get_module(nwbfile, "behavior", "behavior and brain states").add(table)

    def add_position(self, nwbfile: NWBFile, sess_info: dict):
        times, xy, linear = sess_info["position_times"], sess_info["position_xy"], sess_info["position_linear"]
        maze_type = sess_info["maze_type"]
        maze = MAZE_DESCRIPTIONS.get(maze_type, maze_type)
        valid_xy = np.isfinite(xy).all(axis=1)
        nan_linear = float(np.mean(np.isnan(linear[valid_xy])))
        tracking = (
            f" Head position tracked with head-mounted LEDs and a camera at about 39 Hz during the MAZE epoch on "
            f"{maze} ('{maze_type}')."
        )
        position = Position(name="position")
        position.add_spatial_series(
            SpatialSeries(
                name="position_2d",
                description=(
                    "x, y position of the rat in meters (sessInfo.Position.TwoDLocation)." + tracking + " NaN when the "
                    "rat was outside the cameras' field of view or the tracking failed. The orientation of the camera "
                    "frame (which way x and y point in the room) is not documented."
                ),
                data=xy,
                **timing(times),
                reference_frame="camera image, in meters; origin and orientation not documented",
            )
        )
        if maze_type == "Circular Maze":
            toward_lower, toward_higher = running_direction(times, linear)
            linear_description = (
                f"linearized position along the circular track, 0 to {np.nanmax(linear):.2f} m "
                "(sessInfo.Position.OneDLocation). The rat received its water reward at 0 (CRCNS hc-11 description) "
                "and ran mostly toward decreasing linearized position, reaching the reward at 0: of the samples, "
                f"{toward_lower:.0%} move toward lower and {toward_higher:.0%} toward higher values at more than "
                f"{SPEED_THRESHOLD * 100:.0f} cm/s. In the stored x, y coordinates the linearized position increases "
                "counter-clockwise if y points up, so whether it increases clockwise in the room depends on the "
                "camera's orientation, which is not documented."
            )
        else:
            linear_description = (
                f"linearized position along the linear track, 0 to {np.nanmax(linear):.2f} m "
                "(sessInfo.Position.OneDLocation); the rat was rewarded at both ends and ran in both directions."
            )
        position.add_spatial_series(
            SpatialSeries(
                name="linearized_position",
                description=(
                    linear_description
                    + tracking
                    + " The lab defined it only while the rat ran along the track: it is NaN for "
                    f"{nan_linear:.0%} of the samples where the 2D position is known."
                ),
                data=linear,
                **timing(times),
                reference_frame=(
                    "0 is the reward location on the circular track"
                    if maze_type == "Circular Maze"
                    else "0 is one end of the track; which end in the room is not documented"
                ),
            )
        )
        get_module(nwbfile, "behavior", "behavior and brain states").add(position)

    def add_laps(self, nwbfile: NWBFile, sess_info: dict):
        """Laps on the linear tracks from the lab's position_info.mat (pos_inf.in_eps, out_eps and ts_ep)."""
        laps_file_path = self.source_data["laps_file_path"]
        if laps_file_path is None:
            return
        laps = loadmat(str(laps_file_path), simplify_cells=True)["pos_inf"]
        times, linear = sess_info["position_times"], sess_info["position_linear"]
        if not np.allclose(laps["ts"], times):
            raise ValueError(f"The position times of {laps_file_path} are not those of the sessInfo file")
        nwbfile.trials = TimeIntervals(
            name="trials",
            description=(
                "laps on the linear track, from the lab's position_info.mat: the first and last position samples of "
                "each lap (pos_inf.ts_ep)"
            ),
        )
        nwbfile.add_trial_column(
            name="direction",
            description=(
                "the lab's lap label from position_info.mat: 'in' (pos_inf.in_eps) laps run toward increasing "
                "linearized position and 'out' (pos_inf.out_eps) laps toward decreasing linearized position; which "
                "end of the track is which in the room is not documented; 'unlabelled' for laps the lab marked neither in "
                "nor out"
            ),
        )
        track_length = np.nanmax(linear) - np.nanmin(linear)
        for lap_times, is_in, is_out in zip(laps["ts_ep"], laps["in_eps"], laps["out_eps"]):
            lap_times = np.atleast_1d(lap_times)
            if bool(is_in) and bool(is_out):
                raise ValueError(f"A lap of {laps_file_path} is marked both in and out")
            direction = "in" if is_in else "out" if is_out else "unlabelled"
            lap_linear = linear[np.searchsorted(times, lap_times[0]) : np.searchsorted(times, lap_times[-1]) + 1]
            lap_linear = lap_linear[np.isfinite(lap_linear)]
            # A lap that ends (nearly) where it starts has no direction to check against its label
            moved = len(lap_linear) > 1 and abs(lap_linear[-1] - lap_linear[0]) > 0.05 * track_length
            if direction != "unlabelled" and moved and (lap_linear[-1] > lap_linear[0]) != (direction == "in"):
                raise ValueError(f"An {direction} lap of {laps_file_path} runs the other way")
            nwbfile.add_trial(start_time=float(lap_times[0]), stop_time=float(lap_times[-1]), direction=direction)
