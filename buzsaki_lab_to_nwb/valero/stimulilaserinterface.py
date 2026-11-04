"""uLED light pulses of a Valero session (DANDI:000568)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.file import NWBFile

from .valeroutils import build_time_intervals, stimulation_notes

# Per-pulse fields of uLEDPulses.event.mat written as columns: (field, column name, description, dtype)
PULSE_COLUMNS = [
    ("code", "code", "uLED code, 1-12: (shank - 1) * 3 + LED", np.uint8),
    ("shank", "shank", "1-indexed shank of the uLED", np.uint8),
    ("LED", "led", "uLED on the shank, 1-3", np.uint8),
    ("inRipple", "in_ripple", "the pulse fell in a ripple of the ripples table (uLEDPulses.inRipple)", bool),
    (
        "rippleOffset",
        "ripple_offset",
        "time from the start of the ripple to the pulse (s), NaN outside ripples (uLEDPulses.rippleOffset)",
        float,
    ),
    ("inTheta", "in_theta", "the pulse fell in a theta epoch (uLEDPulses.inTheta)", bool),
    (
        "thetaPhase",
        "theta_phase",
        "theta phase at the pulse (radians), NaN outside theta (uLEDPulses.thetaPhase)",
        float,
    ),
    ("velocity", "velocity", "running speed at the pulse, NaN off the track (uLEDPulses.velocity)", float),
    ("manipulated", "manipulated", "the pulse was after the drug injection (uLEDPulses.manipulated)", bool),
    (
        "codeManipulation",
        "code_manipulation",
        "uLED code plus 100 for pulses after the injection (uLEDPulses.codeManipulation)",
        np.uint16,
    ),
]


class ValeroULEDPulsesInterface(BaseDataInterface):
    """All uLED pulses, from uLEDPulses.event.mat.

    No OptogeneticSeries are written: the source gives no light power per pulse (the 2023 conversion wrote the raw
    pulse amplitude as watts). The uLEDs are described by the probe device and the code, shank and LED columns.
    The 2023 conversion used pulses.events.mat, which holds only the pulses of the 6 uLEDs on the analog input
    channels; uLEDPulses.event.mat has the pulses of all 12 uLEDs with their shank, LED and ripple context.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.file_path = self.session_path / f"{self.session_id}.uLEDPulses.event.mat"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.file_path.is_file():
            self.add_analog_pulses(nwbfile)
            return
        pulses = read_mat(str(self.file_path))["uLEDPulses"]
        intervals = np.asarray(pulses["timestamps"], dtype=float)
        order = np.argsort(intervals[:, 0], kind="stable")
        codes = np.asarray(pulses["code"], dtype=int)

        durations = np.diff(intervals, axis=1).ravel()
        n_short = int(np.sum(durations < 0.015))
        per_shank = np.bincount(np.asarray(pulses["shank"], dtype=int), minlength=5)[1:5]
        non_stimulated_shank = np.asarray(pulses.get("nonStimulatedShank", np.nan), dtype=float)
        if non_stimulated_shank.size == 1 and np.isfinite(non_stimulated_shank):
            shank_text = (
                f"Shank {int(non_stimulated_shank)} is the lab's non-stimulated control shank "
                "(uLEDPulses.nonStimulatedShank). "
            )
        else:
            shank_text = ""
        shank_text += "Pulses per shank 1-4: " + ", ".join(str(int(count)) for count in per_shank) + ". "
        manipulation = pulses.get("manipulationInfo", {})
        notes = stimulation_notes(self.session_path)
        description = (
            "uLED pulses from the lab's uLEDPulses.event.mat: 20 ms trapezoid pulses (1 ms rise) of blue light "
            "(460 nm) from 12 uLEDs (3 per shank), delivered by a 12-channel current generator (OSC1Lite) driven by an "
            "Arduino at random uLEDs with random 20-40 ms gaps (the paper), so that onset-to-onset intervals are about "
            "40-60 ms. The paper gives currents of 2-4.5 uA generating 0.02-0.1 uW of total light power; this "
            f"session's uLEDPulses.amplitude is {pulses['amplitude']}"
            + (f" and its folder holds empty files named {', '.join(repr(note) for note in notes)}" if notes else "")
            + "; the light power of the pulses is not in the source. "
            + shank_text
            + f"{n_short} of the {len(durations)} pulses last less than 15 ms, as in the source."
        )
        if manipulation and manipulation.get("effectorType") not in (None, "None"):
            description += (
                f" Manipulation (uLEDPulses.manipulationInfo): effector {manipulation['effectorType']}, injected "
                f"{manipulation['injected']} at {float(manipulation['manipulationTime']):.2f} s."
            )
        columns = []
        for field, name, column_description, dtype in PULSE_COLUMNS:
            if field in pulses:
                columns.append((name, column_description, np.asarray(pulses[field])[order].astype(dtype)))
        table = build_time_intervals(
            "uled_pulses", description, intervals[order, 0], intervals[order, 1], columns=columns
        )
        nwbfile.add_time_intervals(table)
        # The codes have the documented (shank, LED) layout
        assert np.array_equal(codes, (np.asarray(pulses["shank"]) - 1) * 3 + np.asarray(pulses["LED"]))

    def add_analog_pulses(self, nwbfile: NWBFile):
        """Pulses from pulses.events.mat, for sessions without uLEDPulses.event.mat (fCamk2)."""
        file_path = self.session_path / f"{self.session_id}.pulses.events.mat"
        if not file_path.is_file():
            return
        pulses = read_mat(str(file_path), ignore_fields=["intsPeriods"])["pulses"]
        channel_key = next((key for key in ("analogChannel", "analogChannelsList") if key in pulses), None)
        if channel_key is None:
            return
        intervals = np.atleast_2d(np.asarray(pulses["timestamps"], dtype=float))
        order = np.lexsort((np.asarray(pulses[channel_key]), intervals[:, 0]))
        n_repeated = len(intervals) - len(np.unique(np.column_stack((intervals, pulses[channel_key])), axis=0))
        notes = stimulation_notes(self.session_path)
        description = (
            "light pulses detected by the lab on the analog inputs of the recording system (pulses.events.mat). This "
            "session has no uLEDPulses.event.mat, so the uLED (shank and LED) of each pulse is not known, and the "
            "analog inputs carry only some of the 12 uLEDs (in sessions with both files, the analog inputs 3-8 hold "
            "the pulses of 6 uLEDs)"
            + (f"; the folder holds empty files named {', '.join(repr(note) for note in notes)}" if notes else "")
            + (f"; {n_repeated} rows repeat another row's times and channel, as in the source" if n_repeated else "")
        )
        columns = [
            ("analog_channel", "analog input channel of the pulse (pulses.analogChannel)", pulses[channel_key]),
            ("amplitude", "the lab's pulse amplitude (pulses.amplitude), units not given", pulses["amplitude"]),
        ]
        table = build_time_intervals(
            "analog_pulses",
            description,
            intervals[order, 0],
            intervals[order, 1],
            [(name, text, np.asarray(values)[order]) for name, text, values in columns],
        )
        nwbfile.add_time_intervals(table)
