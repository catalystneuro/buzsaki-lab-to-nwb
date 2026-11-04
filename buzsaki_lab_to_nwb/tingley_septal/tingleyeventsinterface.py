"""Sleep states and the lab's ripple and LS HFO detections of a Tingley session (DANDI:000213, DANDI:000218)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.epoch import TimeIntervals

from .tingleyutils import as_intervals, matlab_datenum_to_date, read_event_files, read_mat, read_session_info

# SleepState.ints fields written, and their labels
SLEEP_STATES = {"WAKEstate": "WAKE", "NREMstate": "NREM", "REMstate": "REM", "MAstate": "MA"}

PARAMETER_DESCRIPTIONS = dict(
    thresholds="thresholds [start/stop, peak] in standard deviations of the normalized squared signal",
    durations="duration limits [shortest inter-event interval, longest event] in ms",
    passband="pass band in Hz",
    frequency="LFP sampling rate in Hz",
    EMGfilt="EMG correlation threshold for rejecting events",
)


def _format_parameter(value) -> str:
    array = np.atleast_1d(np.asarray(value))
    if array.dtype.kind in "fiub":
        return (
            "[" + " ".join(f"{item:g}" for item in array.ravel()) + "]" if array.size > 1 else f"{array.ravel()[0]:g}"
        )
    return str(value)


class TingleyEventsInterface(BaseDataInterface):
    """Sleep states from <session>.SleepState.states.mat; ripples and HFOs from the lab's bz_FindRipples files."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_sleep_states(nwbfile)
        self.add_ripple_events(nwbfile)

    def add_sleep_states(self, nwbfile: NWBFile):
        file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"
        if not file_path.is_file():
            return
        sleep_state = read_mat(file_path)["SleepState"]
        rows = [
            (start, stop, label)
            for field, label in SLEEP_STATES.items()
            for start, stop in as_intervals(sleep_state["ints"].get(field, []))
        ]
        parameters = sleep_state.get("detectorparams") or sleep_state.get("detectorparms") or {}
        scored = sleep_state.get("detectiondate")
        manual = sleep_state.get("LastManualUpdate")
        table = TimeIntervals(
            name="sleep_states",
            description=(
                f"Brain states of the session scored by the lab with buzcode's {sleep_state.get('detectorname', 'SleepScoreMaster')} "
                f"(SleepState.states.mat, ints), from the slow-wave power of channel {parameters.get('SWchannum')} and the "
                f"theta power of channel {parameters.get('THchannum')} (0-based) and the EMG estimated from the LFP"
                + (f"; scored on {matlab_datenum_to_date(scored)}" if scored else "")
                + (f", last edited by hand on {matlab_datenum_to_date(manual)}" if manual else "")
                + ". Times are whole seconds, as scored. Labels: WAKE, NREM, REM and MA (microarousal, where scored)."
            ),
        )
        table.add_column(name="label", description="the state: WAKE, NREM, REM or MA")
        for start, stop, label in sorted(rows):
            table.add_row(start_time=float(start), stop_time=float(stop), label=label)
        if len(table):
            get_module(nwbfile, "behavior", "behavior and brain states").add(table)

    def add_ripple_events(self, nwbfile: NWBFile):
        tables = {table["name"]: table for table in read_event_files(self.session_path, self.session_id)}
        if not tables:
            return
        session_info = read_session_info(self.session_path, self.session_id) or {}
        regions = session_info.get("region") or []
        module = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")

        # ripplesNREM and ripplesWAKE are subsets of ripplesALL (the same events, by peak time); they become columns
        subsets = {}
        if "ripplesALL" in tables:
            for name in ("ripplesNREM", "ripplesWAKE"):
                if name in tables and np.isin(tables[name]["peaks"], tables["ripplesALL"]["peaks"]).all():
                    subsets[name] = tables.pop(name)

        for name, events in tables.items():
            channel_text = ""
            if events["ripple_channel"]:
                channel = events["ripple_channel"][0]
                region = regions[channel] if channel < len(regions) else "unknown"
                channel_text = f" Detected on channel {channel} (0-based; sessionInfo.region '{region}')"
                if events["noise_channel"]:
                    noise = events["noise_channel"][0]
                    noise_region = regions[noise] if noise < len(regions) else "unknown"
                    channel_text += (
                        f"; events also present on the noise channel {noise} ('{noise_region}') were rejected "
                        f"({events['n_noise']} noise events in the file)"
                    )
                channel_text += "."
            parameters = events["parameters"]
            parameter_text = "; ".join(
                f"{key} {_format_parameter(parameters[key])} ({description})"
                for key, description in PARAMETER_DESCRIPTIONS.items()
                if key in parameters and np.size(parameters[key]) > 0
            )
            restrict = as_intervals(parameters.get("restrict", []))
            if len(restrict):
                parameter_text += (
                    f"; restrict: {len(restrict)} intervals from {restrict[0, 0]:g} to {restrict[-1, 1]:g} s"
                    + (
                        ", although the events span the whole session"
                        if len(events["intervals"]) and events["intervals"][-1, 1] > restrict[-1, 1] + 1
                        else ""
                    )
                )
            description = (
                f"The lab's {events['what']}, from {events['file_name']}"
                + (f", detected with {events['detector']}" if events["detector"] else "")
                + (f" on {matlab_datenum_to_date(events['detection_date'])}" if events["detection_date"] else "")
                + "."
                + channel_text
                + (
                    f" Detection parameters stored in the file: {parameter_text}."
                    if parameter_text
                    else " The file stores no detection parameters."
                )
                + (
                    " The papers' methods give 120-200 Hz, thresholds of 2 and 5 SD and durations of 15-250 ms; the "
                    "values stored with each detection are written here as they are."
                )
            )
            table = TimeIntervals(name=name, description=description)
            table.add_column(name="peak_time", description="time of the peak power (s)")
            table.add_column(
                name="peak_normed_power", description="peak of the normalized squared band-passed signal, in SD"
            )
            if events["peak_frequency"] is not None:
                table.add_column(name="peak_frequency", description="instantaneous frequency at the peak (Hz)")
            if events["peak_amplitude"] is not None:
                table.add_column(
                    name="peak_amplitude",
                    description="amplitude of the band-passed LFP at the peak, in the LFP's int16 steps (0.195 uV each)",
                )
            for subset_name in subsets if name == "ripplesALL" else ():
                table.add_column(
                    name=f"in_{subset_name}",
                    description=f"the event is also in {subsets[subset_name]['file_name']} ({subsets[subset_name]['what']})",
                )
            subset_peaks = {subset_name: set(subsets[subset_name]["peaks"]) for subset_name in subsets}
            for index in np.argsort(events["intervals"][:, 0], kind="stable"):
                row = dict(
                    start_time=float(events["intervals"][index, 0]),
                    stop_time=float(events["intervals"][index, 1]),
                    peak_time=float(events["peaks"][index]),
                    peak_normed_power=float(events["peak_normed_power"][index]),
                )
                if events["peak_frequency"] is not None:
                    row["peak_frequency"] = float(events["peak_frequency"][index])
                if events["peak_amplitude"] is not None:
                    row["peak_amplitude"] = float(events["peak_amplitude"][index])
                if name == "ripplesALL":
                    for subset_name, peaks in subset_peaks.items():
                        row[f"in_{subset_name}"] = bool(events["peaks"][index] in peaks)
                table.add_row(**row)
            module.add(table)
