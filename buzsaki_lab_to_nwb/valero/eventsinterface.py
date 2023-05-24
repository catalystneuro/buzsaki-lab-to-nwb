from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb import H5DataIO
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile


class ValeroHSUPDownEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        # We use the behavioral cellinfo file to get the trial intervals
        up_down_states_file_path = self.session_path / f"{self.session_id}.UDStates.events.mat"
        assert up_down_states_file_path.exists(), f"Up down states event file not found: {up_down_states_file_path}"

        mat_file = read_mat(up_down_states_file_path, variable_names=["UDStates"])

        up_and_down_states_data = mat_file["UDStates"]

        intervals = up_and_down_states_data["ints"]
        up_intervals = intervals["UP"]
        up_start_time, up_stop_time = up_intervals[:, 0], up_intervals[:, 1]
        down_intervals = intervals["DOWN"]
        down_start_time, down_stop_time = down_intervals[:, 0], down_intervals[:, 1]

        # Combine and sort UP and DOWN intervals
        combined_start_times = np.concatenate((up_start_time, down_start_time))
        combined_stop_times = np.concatenate((up_stop_time, down_stop_time))
        combined_states = np.array(["UP"] * len(up_start_time) + ["DOWN"] * len(down_start_time))

        # Create an array of indices that sorts the start times
        sort_indices = np.argsort(combined_start_times)

        # Sort all arrays using the sorting indices
        combined_start_times = combined_start_times[sort_indices]
        combined_stop_times = combined_stop_times[sort_indices]
        combined_states = combined_states[sort_indices]

        # Create TimeIntervals
        name = "UP_down_states"
        description = "TBD"
        states_intervals = TimeIntervals(name=name, description=description)

        # Add a new column for states
        states_intervals.add_column(name="state", description="State (UP or DOWN)")

        # Add intervals
        for start_time, stop_time, state in zip(combined_start_times, combined_stop_times, combined_states):
            states_intervals.add_interval(start_time=start_time, stop_time=stop_time, state=state)

        processing_module = get_module(nwbfile=nwbfile, name="behavior")
        processing_module.add(states_intervals)


class ValeroHSEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        # We use the behavioral cellinfo file to get the trial intervals
        hse_data_path = self.session_path / f"{self.session_id}.HSE.mat"
        assert hse_data_path.exists(), f"HSE event file not found: {hse_data_path}"

        mat_file = read_mat(hse_data_path, variable_names=["HSE"])
        hse_data = mat_file["HSE"]

        hse_intervals = hse_data["timestamps"]
        peaks = hse_data["peaks"]
        center = hse_data["center"]

        column_descriptions = dict(
            peaks="TBD",
            center="TBD",
        )

        column_data_dict = dict(
            peaks=peaks,
            center=center,
        )

        name = "HSE_events"
        description = "TBD"  # TODO: Ask author for description
        ripple_events_table = TimeIntervals(name=name, description=description)

        for start_time, stop_time in hse_intervals:
            ripple_events_table.add_row(start_time=start_time, stop_time=stop_time)

        for column_name, column_data in column_data_dict.items():
            ripple_events_table.add_column(
                name=column_name,
                description=column_descriptions[column_name],
                data=H5DataIO(column_data, compression="gzip"),
            )

        processing_module = get_module(nwbfile=nwbfile, name="ecephys")

        processing_module.add(ripple_events_table)


class ValeroRipplesEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        # We use the behavioral cellinfo file to get the trial intervals
        ripples_file_path = self.session_path / f"{self.session_id}.ripples.events.mat"
        assert ripples_file_path.exists(), f"Ripples event file not found: {ripples_file_path}"

        mat_file = read_mat(ripples_file_path, variable_names=["ripples"])
        ripples_data = mat_file["ripples"]

        ripple_intervals = ripples_data["timestamps"]

        peaks = ripples_data["peaks"]
        peak_normed_power = ripples_data["peakNormedPower"]

        ripple_stats_data = ripples_data["rippleStats"]["data"]

        peak_frequencies = ripple_stats_data["peakFrequency"]
        ripple_durations = ripple_stats_data["duration"]
        peak_amplitudes = ripple_stats_data["peakAmplitude"]

        descriptions = dict(
            ripple_durations="Duration of the ripple event.",
            peaks="Peak of the ripple.",
            peak_normed_power="Normed power of the peak.",
            peak_frequencies="Peak frequency of the ripple.",
            peak_amplitudes="Peak amplitude of the ripple.",
        )

        name = "ripples_events"
        ripple_events_table = TimeIntervals(name=name, description="Ripples and their metrics")

        for start_time, stop_time in ripple_intervals:
            ripple_events_table.add_row(start_time=start_time, stop_time=stop_time)

        for column_name, column_data in zip(
            list(descriptions), [ripple_durations, peaks, peak_normed_power, peak_frequencies, peak_amplitudes]
        ):
            ripple_events_table.add_column(
                name=column_name,
                description=descriptions[column_name],
                data=H5DataIO(column_data, compression="gzip"),
            )

        # Extract indexed data
        ripple_stats_maps = ripples_data["rippleStats"]["maps"]

        ripple_raw = ripple_stats_maps["ripples_raw"]
        ripple_frequencies = ripple_stats_maps["frequency"]
        ripple_phases = ripple_stats_maps["phase"]
        ripple_amplitudes = ripple_stats_maps["amplitude"]

        indexed_descriptions = dict(
            ripple_raw="Extracted ripple data.",
            ripple_frequencies="Frequency of each point on the ripple.",
            ripple_phases="Phase of each point on the ripple.",
            ripple_amplitudes="Amplitude of each point on the ripple.",
        )

        for column_name, column_data in zip(
            list(indexed_descriptions), [ripple_raw, ripple_frequencies, ripple_phases, ripple_amplitudes]
        ):
            ripple_events_table.add_column(
                name=column_name,
                description=indexed_descriptions[column_name],
                index=list(range(column_data.shape[0])),
                data=H5DataIO(column_data, compression="gzip"),
            )

        processing_module = get_module(nwbfile=nwbfile, name="ecephys")

        processing_module.add(ripple_events_table)
