"""Ripples, high-synchrony events, UP/DOWN states and sleep states of a Valero session (DANDI:000568)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.file import NWBFile

from .valeroutils import build_time_intervals, to_json


class _ValeroEventsInterface(BaseDataInterface):
    suffix = ""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.file_path = self.session_path / f"{self.session_id}{self.suffix}"


class ValeroRipplesEventsInterface(_ValeroEventsInterface):
    suffix = ".ripples.events.mat"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.file_path.is_file():
            return
        ripples = read_mat(str(self.file_path), variable_names=["ripples"])["ripples"]
        intervals = np.atleast_2d(ripples["timestamps"])
        if intervals.size == 0:
            return
        info = ripples.get("detectorinfo", {})
        detector = info.get("detectorname") or ripples.get("detectorName") or "not given"
        parameters = {key: value for key, value in info.get("detectionparms", {}).items() if key != "basepath"}
        durations = np.diff(intervals, axis=1).ravel()
        description = (
            f"ripples detected by the lab with {detector} (ripples.events.mat); median duration "
            f"{np.median(durations) * 1000:.1f} ms; detection parameters: {to_json(parameters)}"
        )
        if detector == "bz_DetectSWR":
            description += (
                ". Unlike the bz_FindRipples ripples of the other sessions, these events come from bz_DetectSWR, "
                "which detects sharp-wave ripples from a sharp-wave channel and a ripple channel together, and are "
                "longer"
            )
        columns = []
        for field, name, column_description in (
            ("peaks", "peak_time", "time of the ripple peak (s)"),
            ("peakNormedPower", "peak_normed_power", "normalized ripple-band power at the peak"),
        ):
            values = np.atleast_1d(ripples.get(field, np.array([])))
            if values.size == len(intervals):
                columns.append((name, column_description, values.astype(float)))
        order = np.argsort(intervals[:, 0], kind="stable")
        table = build_time_intervals(
            "ripples",
            description,
            intervals[order, 0],
            intervals[order, 1],
            [(name, text, values[order]) for name, text, values in columns],
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(table)


class ValeroHSEventsInterface(_ValeroEventsInterface):
    suffix = ".HSE.mat"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.file_path.is_file():
            return
        hse = read_mat(str(self.file_path), variable_names=["HSE"])["HSE"]
        intervals = np.atleast_2d(hse["timestamps"])
        detector = hse.get("detectorinfo", {}).get("detectorname", "not given")
        table = build_time_intervals(
            "high_synchrony_events",
            f"high-synchrony events of the population spiking detected by the lab with {detector} (HSE.mat)",
            intervals[:, 0],
            intervals[:, 1],
            [
                ("peak_time", "time of the peak (s)", np.asarray(hse["peaks"], dtype=float)),
                ("center_time", "time of the center (s)", np.asarray(hse["center"], dtype=float)),
            ],
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(table)


class ValeroHSUPDownEventsInterface(_ValeroEventsInterface):
    suffix = ".UDStates.events.mat"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.file_path.is_file():
            return
        states = read_mat(str(self.file_path), variable_names=["UDStates"])["UDStates"]
        rows = []
        for state in ("UP", "DOWN"):
            intervals = np.asarray(states["ints"].get(state, []), dtype=float)
            if intervals.size == 0:
                continue
            rows += [(start, stop, state) for start, stop in np.reshape(intervals, (-1, 2))]
        if not rows:
            return
        rows.sort()
        table = build_time_intervals(
            "up_down_states",
            "UP (population firing) and DOWN (silent) states detected by the lab (UDStates.events.mat); detection "
            f"parameters: {to_json(states.get('detectionInfo', {}))}",
            [row[0] for row in rows],
            [row[1] for row in rows],
            [("state", "UP or DOWN", [row[2] for row in rows])],
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(table)


# From the 2023 conversion; the *_ThDt states are a second scoring with a higher theta/delta ratio threshold and
# overlap the first
STATE_DESCRIPTIONS = {
    "WAKEstate": "wake",
    "NREMstate": "non-REM sleep",
    "REMstate": "REM sleep",
    "WAKEtheta": "wake with theta",
    "WAKEnontheta": "wake without theta",
    "WAKEtheta_ThDt": "wake with theta, scored with a higher theta/delta ratio",
    "REMtheta_ThDt": "REM sleep with theta, scored with a higher theta/delta ratio",
    "QWake_ThDt": "quiet wake, scored with a higher theta/delta ratio",
    "QWake_noRipples_ThDt": "quiet wake without ripples, scored with a higher theta/delta ratio",
    "NREM_ThDt": "non-REM sleep, scored with a higher theta/delta ratio",
    "NREM_noRipples_ThDt": "non-REM sleep without ripples, scored with a higher theta/delta ratio",
}


class ValeroBehaviorSleepStatesInterface(_ValeroEventsInterface):
    suffix = ".SleepState.states.mat"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.file_path.is_file():
            return
        sleep_state = read_mat(str(self.file_path), variable_names=["SleepState"])["SleepState"]
        rows = []
        for label, intervals in sleep_state["ints"].items():
            intervals = np.asarray(intervals, dtype=float)
            if intervals.size:
                rows += [(start, stop, label) for start, stop in np.reshape(intervals, (-1, 2))]
        if not rows:
            return
        rows.sort()
        info = sleep_state.get("detectorinfo", {})
        windows = info.get("detectionparms", {}).get("MinTimeWindowParms", {})
        present = sorted({row[2] for row in rows})
        n_empty = sum(1 for start, stop, _ in rows if stop <= start)
        table = build_time_intervals(
            "SleepStates",
            f"brain states scored by the lab with {info.get('detectorname', 'SleepScoreMaster')} (buzcode) from the "
            f"LFP slow-wave and theta power and the EMG estimated from the LFP (SleepState.states.mat); minimum "
            f"durations: {to_json(windows)}"
            + (f"; {n_empty} intervals have no duration (stop = start), as in the source" if n_empty else ""),
            [row[0] for row in rows],
            [row[1] for row in rows],
            [
                (
                    "label",
                    "brain state: "
                    + ", ".join(f"{label} ({STATE_DESCRIPTIONS.get(label, label)})" for label in present),
                    [row[2] for row in rows],
                )
            ],
        )
        get_module(nwbfile, "behavior", "behavior and brain states").add(table)
