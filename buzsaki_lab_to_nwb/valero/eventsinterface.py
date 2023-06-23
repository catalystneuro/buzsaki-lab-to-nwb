import json
from pathlib import Path
from warnings import warn

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb import H5DataIO
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile


def get_human_readable_size(file_path):
    size = file_path.stat().st_size
    units = ["B", "KB", "MB", "GB", "TB"]

    # Determine the appropriate unit and scale the size
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    # Format the size with two decimal places and the appropriate unit
    size = round(size, 2)
    formatted_size = f"{size} {units[unit_index]}"

    return formatted_size


class ValeroHSUPDownEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem
        self.file_path = self.session_path / f"{self.session_id}.UDStates.events.mat"

        if verbose and self.file_path.is_file():
            size = get_human_readable_size(self.file_path)
            print(f"The size of {self.file_path.name} is {size}")

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        # We use the behavioral cellinfo file to get the trial intervals
        up_down_states_file_path = self.file_path
        if not up_down_states_file_path.exists():
            warn(f"Up down states event file not found for session {self.session_id}. Skipping interface")
            return nwbfile

        up_down_states_definition = (
            "Up and Down states are a phenomenon observed in neurons, predominantly "
            "in the cerebral cortex, where they spontaneously fluctuate between periods "
            "of high (Up state) and low (Down state) activity. The Up state is characterized "
            "by a high rate of neuronal firing and depolarized membrane potentials, indicating "
            "active information processing. Conversely, the Down state is associated with a "
            "low rate of neuronal firing and hyperpolarized membrane potentials, suggesting "
            "a resting or inactive phase."
        )

        mat_file = read_mat(up_down_states_file_path, variable_names=["UDStates"])
        up_and_down_states_data = mat_file["UDStates"]

        detection_kwargs = up_and_down_states_data["detectionInfo"]
        detection_kwargs_json = json.dumps(detection_kwargs, indent=4)
        description = up_down_states_definition + f"\n\nDetection parameters:\n{detection_kwargs_json}"

        intervals = up_and_down_states_data["ints"]
        up_data_is_an_interval = intervals["UP"].ndim == 2
        down_data_is_an_interval = intervals["DOWN"].ndim == 2

        if up_data_is_an_interval and down_data_is_an_interval:
            self.add_up_and_down_sates_as_intervals(nwbfile, intervals, description)
        else:
            warn(f"Up and down states data is not an interval for session_path: {self.session_id}. Skipping.")

        return nwbfile

    def add_up_and_down_sates_as_intervals(self, nwbfile: NWBFile, intervals, description):
        up_intervals = intervals["UP"]
        down_intervals = intervals["DOWN"]

        up_start_time, up_stop_time = up_intervals[:, 0], up_intervals[:, 1]
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
        name = "UpDownStatesTimeIntervals"

        states_intervals = TimeIntervals(name=name, description=description)

        # Add a new column for states
        states_intervals.add_column(name="state", description="UP or DOWN state")

        # Add intervals
        for start_time, stop_time, state in zip(combined_start_times, combined_stop_times, combined_states):
            states_intervals.add_interval(start_time=start_time, stop_time=stop_time, state=state)

        processing_module = get_module(nwbfile=nwbfile, name="behavior")
        processing_module.add(states_intervals)


class ValeroHSEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        super().__init__(folder_path=folder_path, verbose=verbose)

        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem
        self.file_path = self.session_path / f"{self.session_id}.HSE.mat"

        if verbose and self.file_path.is_file():
            size = get_human_readable_size(self.file_path)
            print(f"The size of {self.file_path.name} is {size}")

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        # We use the behavioral cellinfo file to get the trial intervals
        hse_data_path = self.file_path
        if not hse_data_path.exists():
            warn(f"HSE event file not found: {hse_data_path}. Skipping HSE events interface. \n")
            return nwbfile

        mat_file = read_mat(hse_data_path, variable_names=["HSE"])
        hse_data = mat_file["HSE"]

        hse_intervals = hse_data["timestamps"]
        peaks = hse_data["peaks"]
        center = hse_data["center"]

        mat_field_to_nwb_info = dict()
        mat_field_to_nwb_info["peaks"] = dict(name="peak_time", description="The time of the peak", data=peaks)
        mat_field_to_nwb_info["center"] = dict(name="center_time", description="The time of the center", data=center)

        name = "HSETimeIntervals"
        description = "High synchrony events"  # TODO: Confirm author for description
        ripple_events_table = TimeIntervals(name=name, description=description)

        for start_time, stop_time in hse_intervals:
            ripple_events_table.add_row(start_time=start_time, stop_time=stop_time)

        for field_name, nwb_info in mat_field_to_nwb_info.items():
            ripple_events_table.add_column(
                name=nwb_info["name"],
                description=nwb_info["description"],
                data=H5DataIO(nwb_info["data"], compression="gzip"),
            )

        processing_module = get_module(nwbfile=nwbfile, name="ecephys")

        processing_module.add(ripple_events_table)

        return nwbfile


class ValeroRipplesEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        super().__init__(folder_path=folder_path, verbose=verbose)

        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem
        self.file_path = self.session_path / f"{self.session_id}.ripples.events.mat"

        if verbose and self.file_path.is_file():
            size = get_human_readable_size(self.file_path)
            print(f"The size of {self.file_path.name} is {size}")

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        # We use the behavioral cellinfo file to get the trial intervals
        ripples_file_path = self.file_path
        if not ripples_file_path.exists():
            warn(f"Ripples events file not found for session {self.session_id}. Skipping ripple events interface. \n")

            return nwbfile

        mat_file = read_mat(ripples_file_path, variable_names=["ripples"])
        ripples_data = mat_file["ripples"]

        ripple_intervals = ripples_data["timestamps"]
        if ripple_intervals.size == 0:
            warn(f"\n No ripples found for session: {self.session_id}. Skipping ripple events interface \n")
            return nwbfile

        # Name and descriptions
        mat_field_to_nwb_info = dict()
        if "peaks" in ripples_data and ripples_data["peaks"].size != 0:
            mat_field_to_nwb_info["peaks"] = dict(
                name="peak_time", description="Time at which the ripple peaked.", data=ripples_data["peaks"]
            )

        if "peakNormedPower" in ripples_data and ripples_data["peakNormedPower"].size != 0:
            mat_field_to_nwb_info["peakNormedPower"] = dict(
                name="peak_normed_power",
                description="Normed power of the peak.",
                data=ripples_data["peakNormedPower"],
            )

        if "rippleStats" in ripples_data:
            ripple_stats = ripples_data["rippleStats"]
            if "peakFrequency" in ripple_stats["data"] and ripple_stats["data"]["peakFrequency"].size != 0:
                mat_field_to_nwb_info["peakFrequency"] = dict(
                    name="peak_frequencies",
                    description="Peak frequency of the ripple.",
                    data=ripple_stats["data"]["peakFrequency"],
                )
            if "duration" in ripple_stats["data"] and ripple_stats["data"]["duration"].size != 0:
                mat_field_to_nwb_info["duration"] = dict(
                    name="ripple_durations",
                    description="Duration of the ripple event.",
                    data=ripple_stats["data"]["duration"],
                )
            if "peakAmplitude" in ripple_stats["data"] and ripple_stats["data"]["peakAmplitude"].size != 0:
                mat_field_to_nwb_info["peakAmplitude"] = dict(
                    name="peak_amplitudes",
                    description="Peak amplitude of the ripple.",
                    data=ripple_stats["data"]["peakAmplitude"],
                )

        name = "RippleTimeIntervals"
        ripple_events_table = TimeIntervals(name=name, description="Ripples and their metrics")

        for start_time, stop_time in ripple_intervals:
            ripple_events_table.add_row(start_time=start_time, stop_time=stop_time)

        for field_name, nwb_info in mat_field_to_nwb_info.items():
            ripple_events_table.add_column(
                name=nwb_info["name"],
                description=nwb_info["description"],
                data=H5DataIO(nwb_info["data"], compression="gzip"),
            )

        # Extract indexed data
        if "rippleStats" in ripples_data:
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

        # Add the events to the ecephys processing module
        processing_module = get_module(nwbfile=nwbfile, name="ecephys")
        processing_module.add(ripple_events_table)

        return nwbfile


class ValeroBehaviorSleepStatesInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        super().__init__(folder_path=folder_path, verbose=verbose)

        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem
        self.file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"

        if verbose and self.file_path.is_file():
            size = get_human_readable_size(self.file_path)
            print(f"The size of {self.file_path.name} is {size}")

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        # Sleep states
        sleep_states_file_path = self.file_path
        if not sleep_states_file_path.exists():
            warn(f"Sleep states file {sleep_states_file_path} not found. Skipping sleep states interface")
            return nwbfile

        mat_file = read_mat(sleep_states_file_path)

        sleep_intervals = mat_file["SleepState"]["ints"]
        sleep_intervals = {key: value for key, value in sleep_intervals.items() if value.shape[0] > 0}

        description_of_states = {
            "WAKEstate": "Waked and in locomotion",
            "NREMstate": "Non-REM sleep",
            "REMstate": "Rapid eye movement sleep",
            "WAKEtheta": "Wake with theta",
            "WAKEnontheta": "Wake without theta",
            "WAKEtheta_ThDt": "Wake with theta, estimated with higher theta/delta ratio",
            "REMtheta_ThDt": "REM sleep with theta, estimated with higher theta/delta ratio",
            "QWake_ThDt": "Quiet wakefulness esimated with higher theta/delta ratio",
            "QWake_noRipples_ThDt": "Quite wakefulness without ripples, estimated with higher theta/delta ratio",
            "NREM_ThDt": "Non-REM sleep, estimated with higher theta/delta ratio",
            "NREM_noRipples_ThDt": "Non-REM sleep without ripples, estimated with higher theta/delta ratio",
        }
        description = (
            "Sleep state of the subject."
            "Estimated using `https://github.com/buzsakilab/buzcode/tree/master/detectors/detectStates/SleepScoreMaster`"
        )

        description_of_available_states = {state: description_of_states[state] for state in sleep_intervals}
        description = f"Description of states : {json.dumps(description_of_available_states, indent=4)}"

        table_rows = []
        for state_name, state_intervals in sleep_intervals.items():
            if state_intervals.ndim > 1:
                for start_time, stop_time in state_intervals:
                    row_as_dict = dict(start_time=float(start_time), stop_time=float(stop_time), label=state_name)
                    table_rows.append(row_as_dict)
            else:  # This is necessary because `read_mat` returns a 1D array if there is only one interval
                start_time, stop_time = state_intervals
                row_as_dict = dict(start_time=float(start_time), stop_time=float(stop_time), label=state_name)
                table_rows.append(row_as_dict)

        time_intervals = TimeIntervals(name="SleepStates", description=description)
        time_intervals.add_column(name="label", description="Sleep state.")
        sorted_table = sorted(table_rows, key=lambda x: (x["start_time"], x["stop_time"]))
        [time_intervals.add_row(**row_as_dict) for row_as_dict in sorted_table]

        processing_module = get_module(nwbfile=nwbfile, name="behavior")
        processing_module.add(time_intervals)
