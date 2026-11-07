"""Tracking, temperature, trials, cooling intervals, epochs and sleep states of a Petersen session (DANDI:000059)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile, TimeSeries
from pynwb.behavior import Position, SpatialSeries
from pynwb.epoch import TimeIntervals

from .petersenutils import (
    COOLING_STATE_LABELS,
    TRANSITION_LABEL,
    UNLABELLED,
    as_list,
    intervals,
    read_mat,
    read_session_mat,
    trial_states,
)

# Sessions whose measured septal temperature stays flat although the lab's files label a cooling interval and cooling
# states (session.mat analysisTags.CoolingSession = 1); the paper lists them as control sessions (cooling_session 0)
FLAT_TEMPERATURE_SESSIONS = {"Peter_MS21_180719_155941_concat", "Peter_MS22_180719_122813_concat"}
FLAT_TEMPERATURE_NOTE = (
    " In this session the measured septal temperature (MeasuredTemperature) stays flat through the labelled cooling "
    "interval, so the septum does not appear to have been cooled; the labels are kept as the lab gives them."
)
SLEEP_STATE_MEANINGS = {
    "WAKE": "wake, scored by the lab with SleepScoreMaster (buzcode)",
    "NREM": "non-REM sleep, scored by the lab with SleepScoreMaster (buzcode)",
    "REM": "REM sleep, scored by the lab with SleepScoreMaster (buzcode)",
}


def timing(times: np.ndarray) -> dict:
    """starting_time and rate for evenly spaced times, otherwise the timestamps."""
    steps = np.diff(times)
    if len(steps) and np.allclose(steps, np.median(steps), rtol=0, atol=1e-6):
        return dict(starting_time=float(times[0]), rate=float(round(1 / np.median(steps), 6)))
    return dict(timestamps=times)


class PetersenBehaviorInterface(BaseDataInterface):
    """The lab's animal, trials, temperature, cooling, session and SleepState files of a session folder."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.session = read_session_mat(self.session_path, self.session_id)
        self.choose_behavior_files()

    def file(self, suffix: str) -> Path:
        return self.session_path / f"{self.session_id}{suffix}"

    def choose_behavior_files(self):
        """The buzcode files (<session>.animal.behavior.mat, <session>.trials.behavior.mat), else animal.mat/trials.mat.

        A pair is used only if the trials' sample indices fall within the tracking samples and the trials file has the
        side labels and errors (the newer buzcode layout, with stateNames and states, does not).
        """
        self.animal = self.trials = None
        pairs = [
            (self.file(".animal.behavior.mat"), self.file(".trials.behavior.mat")),
            (self.session_path / "animal.mat", self.session_path / "trials.mat"),
        ]
        for animal_path, trials_path in pairs:
            if not animal_path.is_file():
                continue
            animal = read_mat(animal_path)["animal"]
            trials = read_mat(trials_path)["trials"] if trials_path.is_file() else None
            if trials is not None and np.max(trials["end"]) > len(animal["time"]):
                continue
            # The newer buzcode trials layout (stateNames/states) lacks the side labels and errors read here
            if trials is not None and not {"labels", "stat", "error"} <= set(trials):
                continue
            self.animal, self.trials = animal, trials
            self.animal_file, self.trials_file = animal_path.name, trials_path.name if trials is not None else None
            return

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        if self.animal is not None:
            self.add_tracking(nwbfile)
        self.add_temperature(nwbfile)
        if self.trials is not None:
            self.add_trials(nwbfile)
        self.add_cooling(nwbfile)
        self.add_epochs(nwbfile)
        self.add_sleep_states(nwbfile)

    def add_tracking(self, nwbfile: NWBFile):
        animal = self.animal
        time = np.asarray(animal["time"], dtype=float)
        rate = float(animal["sr"])
        module = get_module(nwbfile, "behavior", "processed behavioral data")
        source = f"from the lab's {self.animal_file}, OptiTrack head tracking at {rate:g} Hz on the recording clock"

        position = SpatialSeries(
            name="SpatialSeries",
            description=f"(x, y, z) head position on the theta maze, in cm, {source}",
            data=np.asarray(animal["pos"], dtype=float).T,
            timestamps=time,
            conversion=0.01,
            reference_frame="the lab's maze coordinates (animal.pos); the origin is not described in the source",
        )
        module.add(Position(name="SubjectPosition", spatial_series=position))
        if "pos_linearized" in animal:
            low, high = as_list(animal.get("pos_linearized_limits", [np.nan, np.nan]))
            module.add(
                Position(
                    name="LinearizedPosition",
                    spatial_series=SpatialSeries(
                        name="LinearizedSpatialSeries",
                        description=(
                            f"position along the lab's linearization of the theta maze (animal.pos_linearized, "
                            f"{low:g} to {high:g} cm), NaN outside the trials, {source}"
                        ),
                        data=np.asarray(animal["pos_linearized"], dtype=float),
                        timestamps=position,
                        conversion=0.01,
                        reference_frame="0 at the start of the lab's linearized maze path",
                    ),
                )
            )
        module.add(
            TimeSeries(
                name="SubjectSpeed",
                description=f"the lab's running speed (animal.speed), {source}",
                data=np.asarray(animal["speed"], dtype=float),
                timestamps=position,
                unit="cm/s",
            )
        )
        module.add(
            TimeSeries(
                name="Acceleration",
                description=(
                    f"the lab's acceleration (animal.acceleration), {source}. The source does not give its unit: in some "
                    "sessions it is the change of speed between consecutive samples (cm/s per sample)"
                ),
                data=np.asarray(animal["acceleration"], dtype=float),
                timestamps=position,
                unit="unknown",
            )
        )

    def add_temperature(self, nwbfile: NWBFile):
        module = get_module(nwbfile, "behavior", "processed behavioral data")
        measured_path = self.session_path / "temperature.mat"
        if measured_path.is_file():
            temperature = read_mat(measured_path)["temperature"]
            module.add(
                TimeSeries(
                    name="MeasuredTemperature",
                    description=(
                        "temperature of the medial septum measured by the thermocouple of the cooling probe (the "
                        "'MS temperature probe' auxiliary input of session.mat), as the lab stored it in temperature.mat "
                        f"at {float(temperature['sr']):g} Hz on the recording clock"
                        + (FLAT_TEMPERATURE_NOTE if self.session_id in FLAT_TEMPERATURE_SESSIONS else "")
                    ),
                    data=np.asarray(temperature["temp"], dtype=float),
                    unit="degrees Celsius",
                    **timing(np.asarray(temperature["time"], dtype=float)),
                )
            )
        elif self.animal is not None and "temperature" in self.animal:
            module.add(
                TimeSeries(
                    name="ModelledTemperature",
                    description=(
                        "NOT A MEASUREMENT. The temperature curve in the lab's animal file (animal.temperature), written "
                        "because the session has no measured temperature. In sessions with a probe recording this "
                        "curve is a model: it drops to 17 degrees C at the cooling onset and recovers exponentially to "
                        "37 degrees C, while the measured temperature (temperature.mat) does not follow it."
                    ),
                    data=np.asarray(self.animal["temperature"], dtype=float),
                    timestamps=nwbfile.processing["behavior"]["SubjectPosition"]["SpatialSeries"],
                    unit="degrees Celsius",
                )
            )

    def cooling_labels(self) -> tuple:
        """Cooling state labels of the trials and a note on how they were aligned."""
        trials = self.trials
        n_trials = len(np.atleast_1d(trials["start"]))
        codes = np.atleast_1d(trials.get("cooling", [])).astype(int)
        labels = [COOLING_STATE_LABELS.get(code, TRANSITION_LABEL if code == 0 else str(code)) for code in codes]
        if len(codes) == n_trials:
            return labels, ""
        if len(codes) > n_trials or "state" not in self.animal:
            return None, f" The lab's file has {len(codes)} cooling codes for {n_trials} trials, so they are left out."
        # The lab's per-sample state vector gives the state of each trial (0 when it has none)
        states = trial_states(np.asarray(self.animal["state"], dtype=float), trials["start"], trials["end"])
        if not np.array_equal(states[: len(codes)], codes):
            return None, f" The lab's file has {len(codes)} cooling codes for {n_trials} trials, so they are left out."
        missing = n_trials - len(codes)
        note = (
            f" The lab's file has {len(codes)} cooling codes for {n_trials} trials; they are the codes of the first "
            f"{len(codes)} trials (checked against the per-sample state vector of {self.animal_file}), and the last "
            f"{missing} trial(s) are '{UNLABELLED}'."
        )
        return labels + [UNLABELLED] * missing, note

    def add_trials(self, nwbfile: NWBFile):
        trials = self.trials
        time = np.asarray(self.animal["time"], dtype=float)
        # The lab's start and end are 1-based MATLAB sample indices of the tracking
        starts = time[np.atleast_1d(trials["start"]).astype(int) - 1]
        stops = time[np.atleast_1d(trials["end"]).astype(int) - 1]
        n_trials = len(starts)
        side_labels = as_list(trials["labels"])
        sides = [side_labels[int(stat) - 1] for stat in np.atleast_1d(trials["stat"])]
        errors = np.zeros(n_trials, dtype=bool)
        errors[np.atleast_1d(trials["error"]).astype(int) - 1] = True  # 1-based trial numbers
        cooling, cooling_note = self.cooling_labels()
        description = (
            f"trials from the lab's {self.trials_file}; start and stop are the times of the lab's "
            f"1-based start and end tracking samples in {self.animal_file}"
        )
        nwbfile.trials = TimeIntervals(
            name="trials", description=description + (cooling_note if cooling is None else "")
        )
        nwbfile.add_trial_column(
            name="condition",
            description=(
                f"side arm of the trial in the lab's {self.trials_file} (stat, labeled {', '.join(side_labels)}); in the "
                "tracking, the rat runs to this side arm in the correct trials and to the other one in the error trials"
            ),
        )
        nwbfile.add_trial_column(
            name="error", description=f"the trial is in the lab's list of error trials (trials.error, 1-based)"
        )
        if cooling is not None:
            nwbfile.add_trial_column(
                name="cooling_state",
                description=(
                    "cooling state of the trial, from the lab's codes (trials.cooling) named by animal.state_labels: "
                    f"1 Pre, 2 Cooling, 3 Post; code 0, '{TRANSITION_LABEL}', marks the transition trials the lab left "
                    "out of every state (between the cooling onset and the start of the cooling interval, and between "
                    "the cooling offset and the start of the next no-cooling interval, in the cooling intervals table)"
                    + cooling_note
                    + (FLAT_TEMPERATURE_NOTE if self.session_id in FLAT_TEMPERATURE_SESSIONS else "")
                ),
            )
        if "temperature" in trials and len(np.atleast_1d(trials["temperature"])) == n_trials:
            nwbfile.add_trial_column(
                name="temperature",
                description="the lab's temperature of the trial (trials.temperature), in degrees C",
            )
        for index in range(n_trials):
            row = dict(start_time=float(starts[index]), stop_time=float(stops[index]))
            row.update(condition=sides[index], error=bool(errors[index]))
            if cooling is not None:
                row["cooling_state"] = cooling[index]
            if "temperature" in nwbfile.trials.colnames:
                row["temperature"] = float(np.atleast_1d(trials["temperature"])[index])
            nwbfile.add_trial(**row)

    def add_cooling(self, nwbfile: NWBFile):
        file_path = self.file(".cooling.manipulation.mat")
        if not file_path.is_file():
            return
        cooling = read_mat(file_path)["cooling"]
        onsets, offsets = as_list(cooling["onsets"]), as_list(cooling["offsets"])
        rows = [(start, stop, "nocooling") for start, stop in intervals(cooling["nocooling"])]
        rows += [(start, stop, "cooling") for start, stop in intervals(cooling["cooling"])]
        reversed_rows = [(start, stop, label) for start, stop, label in rows if not start < stop]
        rows = [row for row in rows if row not in reversed_rows]
        # The gaps the lab left between the onset and the cooling interval and between the offset and the no-cooling one
        transitions = []
        for onset in onsets:
            following = [start for start, _, label in rows if label == "cooling" and start >= onset]
            if following and min(following) > onset:
                transitions.append((onset, min(following), TRANSITION_LABEL))
        for offset in offsets:
            following = [start for start, _, label in rows if label == "nocooling" and start >= offset]
            if following and min(following) > offset:
                transitions.append((offset, min(following), TRANSITION_LABEL))
        table = TimeIntervals(
            name="cooling",
            description=(
                f"the lab's cooling intervals ({file_path.name}): cooling onset at "
                + ", ".join(f"{onset:.3f}" for onset in onsets)
                + " s and offset at "
                + ", ".join(f"{offset:.3f}" for offset in offsets)
                + " s; 'cooling' is the lab's cooling interval, 'nocooling' its no-cooling intervals (before and after), "
                f"and '{TRANSITION_LABEL}' the gaps between them that the lab left out of every state"
                + (FLAT_TEMPERATURE_NOTE if self.session_id in FLAT_TEMPERATURE_SESSIONS else "")
                + "".join(
                    f"; the lab's {label} interval [{start:.3f}, {stop:.3f}] s ends before it starts and is left out"
                    for start, stop, label in reversed_rows
                )
            ),
        )
        table.add_column(name="label", description=f"nocooling, cooling or {TRANSITION_LABEL}")
        for start, stop, label in sorted(rows + transitions):
            table.add_row(start_time=float(start), stop_time=float(stop), label=label)
        nwbfile.add_time_intervals(table)

    def add_epochs(self, nwbfile: NWBFile):
        epochs = self.session.get("epochs")
        if isinstance(epochs, dict):
            epochs = [epochs]
        if not epochs:
            return
        skipped = [str(epoch.get("name")) for epoch in epochs if "startTime" not in epoch or "stopTime" not in epoch]
        description = "the recordings (epochs) of the concatenated session, from the lab's session.mat"
        if skipped:
            description += f"; left out because session.mat gives no start or stop time: {', '.join(skipped)}"
        if len(skipped) == len(epochs):
            return
        nwbfile.epochs = TimeIntervals(name="epochs", description=description)
        for name, description in (
            ("recording", "name of the recording (subfolder) of the concatenated session"),
            ("behavioral_paradigm", "the lab's behavioral paradigm of the epoch (session.mat epochs)"),
            ("environment", "the lab's environment of the epoch (session.mat epochs)"),
            ("manipulation", "the lab's manipulation of the epoch (session.mat epochs); empty if none"),
        ):
            nwbfile.add_epoch_column(name=name, description=description)

        def text(value):
            return value if isinstance(value, str) else ""

        for epoch in epochs:
            if str(epoch.get("name")) in skipped:
                continue
            nwbfile.add_epoch(
                start_time=float(epoch["startTime"]),
                stop_time=float(epoch["stopTime"]),
                recording=text(epoch.get("name")),
                behavioral_paradigm=text(epoch.get("behavioralParadigm")),
                environment=text(epoch.get("environment")),
                manipulation=text(epoch.get("manipulation")),
            )

    def add_sleep_states(self, nwbfile: NWBFile):
        file_path = self.file(".SleepState.states.mat")
        if not file_path.is_file():
            return
        states = read_mat(file_path)["SleepState"]["ints"]
        rows = []
        for key, values in states.items():
            label = key.removesuffix("state")
            for start, stop in np.reshape(np.asarray(values, dtype=float), (-1, 2)):
                rows.append((start, stop, label))
        note = ""
        if nwbfile.trials is not None:
            trial_starts, trial_stops = nwbfile.trials["start_time"][:], nwbfile.trials["stop_time"][:]
            asleep = sum(
                max(0.0, min(stop, trial_stop) - max(start, trial_start))
                for start, stop, label in rows
                if label != "WAKE"
                for trial_start, trial_stop in zip(trial_starts, trial_stops)
            )
            if asleep > 0:
                note = (
                    f" The scoring labels {asleep:.0f} s of the maze trials as sleep, which suggests it is not reliable "
                    "during the maze epoch; the states are kept as the lab gives them."
                )
        table = TimeIntervals(
            name="sleep_states",
            description=(
                f"the lab's brain states ({file_path.name}, SleepState.ints, in whole seconds): "
                + "; ".join(
                    f"{label}: {SLEEP_STATE_MEANINGS.get(label, 'not described')}"
                    for label in sorted({row[2] for row in rows})
                )
                + "."
                + note
            ),
        )
        table.add_column(name="label", description="WAKE, NREM or REM")
        for start, stop, label in sorted(rows):
            table.add_row(start_time=start, stop_time=stop, label=label)
        get_module(nwbfile, "behavior", "processed behavioral data").add(table)
