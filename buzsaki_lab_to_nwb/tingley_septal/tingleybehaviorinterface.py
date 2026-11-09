"""Position, head orientation, trials and the lab's trial templates of a Tingley session (DANDI:000213, DANDI:000218)."""

from pathlib import Path

import numpy as np
from hdmf.common import DynamicTable
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile, TimeSeries
from pynwb.epoch import TimeIntervals
from pynwb.behavior import CompassDirection, Position, SpatialSeries

from .tingleyutils import as_intervals, as_list, read_mat

# Metres per unit of the behavior.mat `units` field
CONVERSIONS = {"m": 1.0, "meter": 1.0, "meters": 1.0, "mm": 1e-3, "cm": 1e-2}
# Nominal frame rates of the tracking systems (Tingley and Buzsaki 2018): Basler camera 30 Hz, OptiTrack 120 Hz
NOMINAL_RATES = {"led": 30.0, "optitrack": 120.0}


def round_significant(values: np.ndarray, digits: int = 5) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    rounded = np.zeros_like(values)
    nonzero = values != 0
    scale = 10 ** (digits - 1 - np.floor(np.log10(np.abs(values[nonzero]))))
    rounded[nonzero] = np.round(values[nonzero] * scale) / scale
    return rounded


def rebuild_rounded_timestamps(timestamps: np.ndarray, rates: list):
    """Frame times i / rate when the stored timestamps are exactly those times rounded to 5 significant digits.

    Returns (timestamps, rate), or (the stored timestamps, None) if no rate reproduces every stored value.
    """
    timestamps = np.asarray(timestamps, dtype=float)
    if timestamps.size < 2 or timestamps[0] != 0 or np.all(np.diff(timestamps) > 0):
        return timestamps, None
    frames = np.arange(timestamps.size)
    for rate in rates:
        candidate = frames / rate
        exact = np.isclose(round_significant(candidate), timestamps, rtol=0, atol=1e-9)
        # A frame time on a rounding tie (e.g. 14835.5 s) can round either way, depending on floating-point detail
        # (DT2-20160222 and 20160226 have 256 and 6,823 such frames); within half a rounding unit is a match too
        unit = np.zeros_like(candidate)
        nonzero = candidate != 0
        unit[nonzero] = 10 ** (np.floor(np.log10(np.abs(candidate[nonzero]))) - 4)
        tie = np.abs(candidate - timestamps) <= unit / 2 * (1 + 1e-9)
        if np.all(exact | tie):
            return candidate, rate
    return timestamps, None


def read_behavior(file_path: Path) -> dict:
    """The lab's behavior.mat, whose layout varies between rats, in one form."""
    behavior = read_mat(file_path)["behavior"]
    info = behavior.get("behaviorinfo", {})
    position = behavior["position"]
    orientation = behavior.get("orientation", {})
    units = behavior.get("units") or position.get("units") or ""
    events = behavior["events"]
    trials = events["trials"] if isinstance(events["trials"], list) else [events["trials"]]
    templates = events.get("map", [])
    templates = templates if isinstance(templates, list) else [templates]
    description = behavior.get("description")
    return dict(
        timestamps=np.asarray(behavior["timestamps"], dtype=float).ravel(),
        sampling_rate=float(behavior["samplingRate"]),
        xyz=[np.asarray(position[axis], dtype=float).ravel() for axis in "xyz" if np.size(position.get(axis, [])) > 0],
        units=str(units),
        orientation={
            key: np.asarray(value, dtype=float).ravel()
            for key, value in orientation.items()
            if not isinstance(value, str) and np.size(value) > 0
        },
        rotation_type=str(behavior.get("rotationType") or orientation.get("rotationType") or ""),
        error_per_marker=np.asarray(
            behavior.get("errorPerMarker", info.get("errorPerMarker", [])), dtype=float
        ).ravel(),
        description=description if isinstance(description, str) else "",
        tracking=str(behavior.get("trackingType") or info.get("acquisitionsystem") or "").lower(),
        trials=trials,
        intervals=as_intervals(events["trialIntervals"]),
        conditions=np.asarray(events.get("trialConditions", []), dtype=int).ravel(),
        condition_types=[str(value) for value in as_list(events.get("conditionType"))],
        templates=templates,
    )


class TingleyBehaviorInterface(BaseDataInterface):
    """Tracking, trials and per-condition templates from the lab's <session>.behavior.mat."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.file_path = self.session_path / f"{self.session_id}.behavior.mat"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.file_path.is_file():
            return
        behavior = read_behavior(self.file_path)
        module = get_module(nwbfile, "behavior", "behavior and brain states")
        timestamps, rate = self.add_tracking(nwbfile, module, behavior)
        self.add_trials(nwbfile, module, behavior, timestamps, rate)

    def add_tracking(self, nwbfile: NWBFile, module, behavior: dict):
        tracking = behavior["tracking"]
        stored = behavior["timestamps"]
        nominal = NOMINAL_RATES.get(tracking)
        timestamps, rate = rebuild_rounded_timestamps(stored, [r for r in (nominal, behavior["sampling_rate"]) if r])
        if rate is not None:
            time_note = (
                f" The lab's timestamps are rounded to 5 significant digits (so to 1 s after 10,000 s, with repeated "
                f"values); every one of them equals the frame time i / {rate:g} Hz rounded to 5 digits, so the "
                f"times are rebuilt as frames at {rate:g} Hz from 0 s (the camera's frame rate). The lab's samplingRate "
                f"({behavior['sampling_rate']:.6f} Hz) is the number of frames over the last rounded timestamp; i / "
                "samplingRate does not reproduce the stored values."
            )
        start = 0.0
        if rate is None and nominal and timestamps.size > 1:
            regular = timestamps[0] + np.arange(timestamps.size) / nominal
            if np.allclose(timestamps, regular, rtol=0, atol=1e-6):
                rate, start = nominal, float(timestamps[0])
                time_note = (
                    f" The lab's timestamps (behavior.timestamps) are regular at {nominal:g} Hz from {start:g} s "
                    "(within 1 us), so they are written as a starting time and rate."
                )
            else:
                time_note = " Timestamps are the lab's (behavior.timestamps)."
        elif rate is None:
            time_note = " Timestamps are the lab's (behavior.timestamps)."
        unit = behavior["units"]
        xyz = behavior["xyz"]
        axes = "xyz"[: len(xyz)]
        if tracking == "optitrack":
            system = (
                "OptiTrack Motive: infrared markers on the head stage imaged by six Flex 3 cameras above the maze, "
                "reconstructed in 3D at 120 Hz"
            )
            frame = "OptiTrack calibrated room coordinates; the origin and axis directions are not stored in the source"
        else:
            system = "a Basler camera above the maze (30 Hz) tracking two head-mounted LEDs (one blue, one red)"
            frame = "camera image, in pixels; the origin and orientation of the image are not stored in the source"
        if unit in CONVERSIONS:
            nwb_unit, conversion, unit_note = "meters", CONVERSIONS[unit], f"stored in the lab's unit, {unit}"
        else:
            nwb_unit, conversion = unit or "unknown", 1.0
            unit_note = f"in {unit or 'unstated units'}: the source has no scale to metres"
        position = Position(name="position")
        position.add_spatial_series(
            SpatialSeries(
                name="head_position",
                description=(
                    f"({', '.join(axes)}) position of the head tracked by {system} (behavior.position of the lab's "
                    f"behavior.mat), {unit_note}. Values are the lab's, including NaN for untracked frames and large "
                    "outliers in some sessions." + time_note
                ),
                data=np.column_stack(xyz),
                unit=nwb_unit,
                **(dict(starting_time=start, rate=rate) if rate is not None else dict(timestamps=timestamps)),
                conversion=conversion,
                reference_frame=frame,
            )
        )
        module.add(position)

        same_timing = (
            dict(starting_time=start, rate=rate) if rate is not None else dict(timestamps=position["head_position"])
        )
        orientation = behavior["orientation"]
        if behavior["rotation_type"] == "quaternion" and all(key in orientation for key in "xyzw"):
            module.add(
                TimeSeries(
                    name="head_orientation",
                    description=(
                        "orientation of the head-stage marker set as a unit quaternion (x, y, z, w), from OptiTrack "
                        "Motive (behavior.orientation); dimensionless" + time_note.replace(" Timestamps", " The times")
                    ),
                    data=np.column_stack([orientation[key] for key in "xyzw"]),
                    unit="dimensionless",
                    **same_timing,
                )
            )
        elif "yaw" in orientation:
            yaw = orientation["yaw"]
            n_frames = timestamps.size
            if yaw.size == n_frames:
                yaw_timing, yaw_note = same_timing, ""
            elif yaw.size == 4 * (n_frames - 1) + 1:
                # 4 samples per frame interval: the lab's yaw is interpolated between the frames
                yaw_timing = (
                    dict(starting_time=start, rate=4 * rate)
                    if rate is not None
                    else dict(timestamps=np.interp(np.arange(yaw.size) / 4, np.arange(n_frames), timestamps))
                )
                yaw_note = (
                    f"; the source has {yaw.size} yaw values for {n_frames} frames, 4 per frame interval (4(n-1)+1), "
                    "so they are taken as interpolated by the lab at 4 times the frame rate, from the first to the "
                    "last frame"
                )
            else:
                yaw_timing = None
            if yaw_timing is not None:
                in_radians = np.nanmax(np.abs(yaw)) <= 2 * np.pi + 1e-9
                compass = CompassDirection(name="head_direction")
                compass.add_spatial_series(
                    SpatialSeries(
                        name="head_yaw",
                        description=(
                            "head direction (Euler yaw) from the two head-mounted LEDs (behavior.orientation.yaw; "
                            "pitch and roll are empty in the source), in the camera image frame, values from "
                            f"{np.nanmin(yaw):.3g} to {np.nanmax(yaw):.3g}"
                            + ("; within +-2 pi, so radians" if in_radians else "; unit not stated")
                            + yaw_note
                        ),
                        data=yaw,
                        unit="radians" if in_radians else "unknown",
                        reference_frame=frame,
                        **yaw_timing,
                    )
                )
                module.add(compass)

        error = behavior["error_per_marker"]
        if error.size == timestamps.size:
            module.add(
                TimeSeries(
                    name="error_per_marker",
                    description=(
                        "OptiTrack Motive's mean marker error of the tracked marker set, in the same unit as the "
                        f"position ({unit}: the values scale with it, e.g. 0.1-11 in mm sessions and 1e-4 in m sessions)"
                    ),
                    data=error,
                    unit=nwb_unit,
                    conversion=conversion,
                    **same_timing,
                )
            )
        return timestamps, rate

    def add_trials(self, nwbfile: NWBFile, module, behavior: dict, timestamps: np.ndarray, rate):
        intervals = behavior["intervals"]
        trials = behavior["trials"]
        if len(intervals) == 0:
            return
        if len(trials) != len(intervals):
            raise ValueError(f"{self.file_path.name} has {len(trials)} trials but {len(intervals)} trial intervals")
        conditions = behavior["conditions"]
        condition_types = behavior["condition_types"]
        stored = behavior["timestamps"]
        xyz = behavior["xyz"]

        # The samples of each trial in the session's tracking, to give them the session's (rebuilt) timestamps
        sample_times, not_found, offsets = [], 0, []
        for trial in trials:
            trial_times = np.asarray(trial["timestamps"], dtype=float).ravel()
            if np.size(trial["mapping"]) != trial_times.size:
                raise ValueError(f"A trial of {self.file_path.name} has a mapping and timestamps of different lengths")
            trial_xyz = [np.asarray(trial[axis], dtype=float).ravel() for axis in "xyz"[: len(xyz)]]
            start = None
            for candidate in np.flatnonzero(stored == trial_times[0]):
                block = slice(candidate, candidate + trial_times.size)
                if block.stop <= stored.size and all(
                    np.array_equal(session[block], own, equal_nan=True) for session, own in zip(xyz, trial_xyz)
                ):
                    start = candidate
                    break
            if start is None:
                not_found += 1
                sample_times.append(trial_times)
            else:
                sample_times.append(timestamps[start : start + trial_times.size])
        for (start_time, _), times in zip(intervals, sample_times):
            offsets.append(abs(times[0] - start_time))

        description = (
            f"Trials of the session's task ('{behavior['description']}'): only ballistic runs, without stopping or "
            "leaving the trained path, were kept by the lab (about 90-95% of the attempted trials). Start and stop "
            "times are the lab's behavior.events.trialIntervals; the rows are sorted by start time, each with its own "
            "labels (the earlier conversion sorted the rows but not the labels)."
        )
        sorted_intervals = intervals[np.argsort(intervals[:, 0], kind="stable")]
        n_repeated = len(sorted_intervals) - len(np.unique(sorted_intervals, axis=0))
        n_overlapping = int(np.sum(sorted_intervals[1:, 0] < sorted_intervals[:-1, 1])) - n_repeated
        if n_repeated:
            description += (
                f" {n_repeated} trial(s) repeat another trial's interval and labels exactly (the source lists them "
                "twice); they are kept."
            )
        if n_overlapping > 0:
            description += f" {n_overlapping} trial(s) overlap the previous trial in time, as in the source."
        if not_found:
            description += (
                f" The samples of {not_found} trial(s) are not found in the session's tracking (the trial's positions "
                "differ from behavior.position), so their linearized_position_timestamps are the trial's own timestamps."
            )
        if offsets and max(offsets) > 2 / behavior["sampling_rate"]:
            description += (
                f" The trial start times differ from the rebuilt time of each trial's first tracking sample by up to "
                f"{max(offsets):.2f} s (median {np.median(offsets):.2f} s): the source does not say which clock the "
                "trialIntervals are on."
            )
        nwbfile.trials = TimeIntervals(name="trials", description=description)
        has_direction = any(trial.get("direction") for trial in trials)
        has_type = any(trial.get("type") for trial in trials)
        nwbfile.add_trial_column(
            name="condition",
            description=(
                "the trial's condition (behavior.events.trialConditions): the 1-based row of the trial_conditions "
                "table, whose template the trial was linearized on"
            ),
        )
        if condition_types:
            nwbfile.add_trial_column(
                name="condition_type",
                description="the lab's type of the trial's condition (behavior.events.conditionType)",
            )
        if has_direction:
            nwbfile.add_trial_column(
                name="direction",
                description="the lab's running direction of the trial on the circular maze (trials{i}.direction)",
            )
        if has_type:
            nwbfile.add_trial_column(name="trial_type", description="the lab's task of the trial (trials{i}.type)")
        nwbfile.add_trial_column(
            name="linearized_position",
            description=(
                "the lab's linearization of the trial (trials{i}.mapping): for each tracking sample of the trial, the "
                "1-based index of the nearest point of its condition's template (trial_conditions)"
            ),
            index=True,
        )
        nwbfile.add_trial_column(
            name="linearized_position_timestamps",
            description="times (s) of the samples of linearized_position",
            index=True,
        )
        order = np.argsort(intervals[:, 0], kind="stable")  # rows and their labels sorted together
        for index in order:
            trial = trials[index]
            row = dict(
                start_time=float(intervals[index, 0]),
                stop_time=float(intervals[index, 1]),
                condition=int(conditions[index]),
                linearized_position=np.asarray(trial["mapping"], dtype=int).ravel(),
                linearized_position_timestamps=np.asarray(sample_times[index], dtype=float),
            )
            if condition_types:
                row["condition_type"] = condition_types[int(conditions[index]) - 1]
            if has_direction:
                row["direction"] = str(trial.get("direction", ""))
            if has_type:
                row["trial_type"] = str(trial.get("type", ""))
            nwbfile.add_trial(**row)

        templates = behavior["templates"]
        if templates:
            table = DynamicTable(
                name="trial_conditions",
                description=(
                    "The lab's trial conditions (behavior.events.map and conditionType): each condition's template "
                    "path, a sequence of points on which the trials of the condition are linearized "
                    "(trials.linearized_position). Coordinates are in the unit and frame of the position "
                    f"({behavior['units']}); how the lab built the templates is not stored in the source."
                ),
            )
            table.add_column(name="condition", description="1-based condition number (trials.condition)")
            if condition_types:
                table.add_column(name="condition_type", description="the lab's type of the condition (conditionType)")
            axes = [axis for axis in "xyz" if np.size(templates[0].get(axis, [])) > 0]
            ragged = len({np.size(template[axes[0]]) for template in templates}) > 1
            for axis in axes:
                table.add_column(
                    name=f"template_{axis}", description=f"{axis} of each point of the template", index=ragged
                )
            for number, template in enumerate(templates, 1):
                row = dict(condition=number)
                if condition_types:
                    row["condition_type"] = condition_types[number - 1]
                for axis in axes:
                    row[f"template_{axis}"] = np.asarray(template[axis], dtype=float).ravel()
                table.add_row(**row)
            module.add(table)
