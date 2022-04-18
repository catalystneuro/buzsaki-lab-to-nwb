"""Authors: Heberto Mayorquin and Cody Baker."""
from pathlib import Path

from scipy.io import loadmat
from pynwb import NWBFile, H5DataIO
from pynwb.file import TimeIntervals
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.tools.nwb_helpers import get_module
from nwb_conversion_tools.utils import FilePathType


class SleepStateInterface(BaseDataInterface):
    """Data interface for handling ripples.mat files for the Tingley metabolic project."""

    def __init__(self, mat_file_path: FilePathType):
        super().__init__(mat_file_path=mat_file_path)

    def run_conversion(self, nwbfile: NWBFile):
        processing_module = get_module(
            nwbfile=nwbfile,
            name="ecephys",
            description="Intermediate data from extracellular electrophysiology recordings, e.g., LFP.",
        )

        if Path(self.source_data["mat_file_path"]).exists():
            mat_file = loadmat(self.source_data["mat_file_path"])

            mat_data = mat_file["ripples"]
            start_and_stop_times = mat_data["timestamps"][0][0]
            durations = [x[0] for x in mat_data["data"][0][0]["duration"][0][0]]
            peaks = [x[0] for x in mat_data["peaks"][0][0]]
            peak_normed_powers = [x[0] for x in mat_data["peakNormedPower"][0][0]]
            peak_frequencies = [x[0] for x in mat_data["data"][0][0]["peakFrequency"][0][0]]
            peak_amplitudes = [x[0] for x in mat_data["data"][0][0]["peakAmplitude"][0][0]]
            ripples = mat_data["maps"][0][0]["ripples"][0][0]
            frequencies = mat_data["maps"][0][0]["frequency"][0][0]
            phases = mat_data["maps"][0][0]["phase"][0][0]
            amplitudes = mat_data["maps"][0][0]["amplitude"][0][0]

            descriptions = dict(
                duration="Duration of the ripple event.",
                peak="Peak of the ripple.",
                peak_normed_power="Normed power of the peak.",
                peak_frequency="Peak frequency of the ripple.",
                peak_amplitude="Peak amplitude of the ripple.",
            )
            indexed_descriptions = dict(
                ripple="Extracted ripple data.",
                frequency="Frequency of each point on the ripple.",
                phase="Phase of each point on the ripple.",
                amplitude="Amplitude of each point on the ripple.",
            )

            table = TimeIntervals(name="Ripples", description="Identified ripple events and their metrics.")
            for start_time, stop_time in start_and_stop_times:
                table.add_row(start_time=start_time, stop_time=stop_time)
            for column_name, column_data in zip(
                list(descriptions), [durations, peaks, peak_normed_powers, peak_frequencies, peak_amplitudes]
            ):
                table.add_column(name=column_name, description=descriptions[column_name], data=H5DataIO(column_data))
            for column_name, column_data in zip(list(indexed_descriptions), [ripples, frequencies, phases, amplitudes]):
                table.add_column(
                    name=column_name,
                    description=indexed_descriptions[column_name],
                    index=list(range(column_data.shape[0])),
                    data=H5DataIO(column_data),
                )
            processing_module.add(table)