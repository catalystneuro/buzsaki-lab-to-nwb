from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from neuroconv.tools.nwb_helpers import get_module
import numpy as np
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile
from pymatreader import read_mat


class HuszarProcessingRipplesEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        # We use the behavioral cellinfo file to get the trial intervals
        ripples_file_path = self.session_path / f"{self.session_id}.ripples.events.mat"
        assert ripples_file_path.exists(), f"Ripples event file not found: {ripples_file_path}"

        mat_file = read_mat(ripples_file_path)
        ripples_data = mat_file["ripples"]

        ripple_intervals = ripples_data["timestamps"]

        peaks = ripples_data["peaks"]
        peak_normed_power = ripples_data["peakNormedPower"]

        ripple_stats_data = ripples_data["data"]  # NOTE: Different from Valero Ripples Interface...

        peak_frequencies = ripple_stats_data["peakFrequency"]
        ripple_durations = ripple_stats_data["duration"]
        peak_amplitudes = ripple_stats_data["peakAmplitude"]

        descriptions = dict(
            ripple_durations="Duration of the ripple, in seconds.",
            peaks="Time of the ripple peak, in seconds.",
            peak_normed_power="Normalized ripple-band power at the peak.",
            peak_frequencies="Peak frequency of the ripple, in Hz.",
            peak_amplitudes="Peak amplitude of the ripple, in the lab's units.",
        )

        name = "Ripples"
        detector = ripples_data.get("detectorinfo", {})
        parameters = detector.get("detectionparms", {})
        ripple_events_table = TimeIntervals(
            name=name,
            description=(
                f"sharp-wave ripples detected by the lab with {detector.get('detectorname', 'bz_FindRipples')} "
                f"(passband {parameters.get('passband', [130, 200])} Hz, thresholds {parameters.get('thresholds', '')} "
                "SD) and their metrics, from ripples.events.mat"
            ),
        )

        for start_time, stop_time in ripple_intervals:
            ripple_events_table.add_row(start_time=float(start_time), stop_time=float(stop_time))

        for column_name, column_data in zip(
            list(descriptions), [ripple_durations, peaks, peak_normed_power, peak_frequencies, peak_amplitudes]
        ):
            ripple_events_table.add_column(
                name=column_name, description=descriptions[column_name], data=np.asarray(column_data)
            )

        # Extract indexed data
        ripple_stats_maps = ripples_data["maps"]

        ripple_raw = ripple_stats_maps["ripples"]  # NOTE: Different from Valero Ripples Interface...
        ripple_frequencies = ripple_stats_maps["frequency"]
        ripple_phases = ripple_stats_maps["phase"]
        ripple_amplitudes = ripple_stats_maps["amplitude"]

        n_samples = ripple_raw.shape[1]
        map_note = f" ({n_samples} samples per ripple, centred on the peak, from the lab's ripples.events.mat maps)"
        map_descriptions = dict(
            ripple_raw="Ripple-band LFP around each ripple" + map_note,
            ripple_frequencies="Instantaneous frequency around each ripple, in Hz" + map_note,
            ripple_phases="Ripple-band phase around each ripple, in radians" + map_note,
            ripple_amplitudes="Ripple-band amplitude around each ripple" + map_note,
        )

        # One row of samples per ripple. (The 2023 conversion wrote these as ragged columns with an index of 0 to n-1,
        # which shifted every row by one and dropped the last ripple's samples.)
        for column_name, column_data in zip(
            list(map_descriptions), [ripple_raw, ripple_frequencies, ripple_phases, ripple_amplitudes]
        ):
            ripple_events_table.add_column(
                name=column_name, description=map_descriptions[column_name], data=np.asarray(column_data)
            )

        processing_module = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")

        processing_module.add(ripple_events_table)
