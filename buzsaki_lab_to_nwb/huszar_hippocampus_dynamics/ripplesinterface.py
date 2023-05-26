from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from neuroconv.tools.nwb_helpers import get_module
from pynwb import H5DataIO
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile
from pymatreader import read_mat


class HuszarProcessingRipplesEventsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
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

        ripple_stats_data = ripples_data["data"] # NOTE: Different from Valero Ripples Interface...

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
        ripple_stats_maps = ripples_data["maps"]

        ripple_raw = ripple_stats_maps["ripples"] # NOTE: Different from Valero Ripples Interface...
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