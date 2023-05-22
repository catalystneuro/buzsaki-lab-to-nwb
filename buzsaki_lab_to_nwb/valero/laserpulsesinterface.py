from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile


class ValeroLaserPulsesInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        pulses_data_path = self.session_path / f"{self.session_id}.pulses.events.mat"
        assert pulses_data_path.is_file(), pulses_data_path
        mat_file = read_mat(pulses_data_path)
        pulses_data = mat_file["pulses"]

        pulse_intervals = pulses_data["timestamps"]
        electrode_channel = pulses_data["analogChannel"]
        amplitude = pulses_data["amplitude"]

        current = "2-4.5 μA"
        light_power = "0.02-0.1μW"
        reference = "(15)"
        generator = "OSC1Lite, NeuroNex Michigan Hub"
        arduino_link = "https://github.com/valegarman"
        rise_time = "1ms"
        light_type = "blue light"
        emission = "460 nm"
        area = "150 mm2"
        pulse_duration = "20 ms"
        offset = "40-60ms"

        laser_description = f"""
        μLEDs were controlled with current ({current} generating {light_power} of total light power;
        ref {reference}) provided by a 12-channel current generator ({generator})
        driven by an Arduino ({arduino_link}), which delivered trapezoid ({rise_time} rise time)
        {light_type} (centered emission at {emission}, emission surface area = {area}) {pulse_duration} pulses at
        random sites with a randomly variable ({offset}) offset.
        """

        stimuli_laser_pulses = TimeIntervals(
            name="stimuli_laser_pulses",
            description=laser_description,
        )

        stimuli_laser_pulses.add_column(name="electrode_channel", description="The electrode channel for the pulse")
        stimuli_laser_pulses.add_column(name="amplitude", description="The amplitude of the pulse")

        for interval, channel, amp in zip(pulse_intervals, electrode_channel, amplitude):
            start_time, stop_time = interval
            channel = channel
            row_dict = dict(start_time=start_time, stop_time=stop_time, electrode_channel=channel, amplitude=amp)
            stimuli_laser_pulses.add_row(**row_dict)

        nwbfile.add_time_intervals(stimuli_laser_pulses)
