from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile
from pynwb.ogen import OptogeneticSeries, OptogeneticStimulusSite


class VeleroOptogeneticStimuliInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        pulses_data_path = self.session_path / f"{self.session_id}.pulses.events.mat"
        assert pulses_data_path.is_file(), f"{pulses_data_path} not found"

        mat_file = read_mat(pulses_data_path)
        pulses_data = mat_file["pulses"]
        pulse_intervals = pulses_data["timestamps"]
        pulse_micro_led = pulses_data["analogChannel"]
        pulse_amplitude = pulses_data["amplitude"]

        # Create device
        manufacturer = "Neurolight Technologies"
        name = "N1-F21-O36 | 18"
        description = (
            "12 µLEDs, 10 x 15 µm each, 3 per shank\n"
            "Emission Peak λ = 460 nm and FWHM = 40 nm\n"
            "Typical irradiance of 33 mW/mm² (@ max operating current of 100 µA)\n"
            "32 recording channels, 8 per shank\n"
            "Electrode impedance of 1000 - 1500 kΩ at 1 kHz\n"
        )

        device_metadata = dict(name=name, description=description, manufacturer=manufacturer)
        if device_metadata["name"] not in nwbfile.devices:
            neurolight_probe = nwbfile.create_device(**device_metadata)

        # Create the sites
        site_description = "microscopic LED 10 x 15 µm each, 3 per shank. Each μLED has an emission area of 150 μm2"
        location = "dorsal right hippocampus (antero-posterior 2.0 mm, mediolateral 1.5 mm, dorsoventral 0.6 mm)"

        micro_led_ids_to_site = dict()
        micro_led_ids = np.unique(pulse_micro_led)

        for id in micro_led_ids:
            optogenetic_site = OptogeneticStimulusSite(
                name=f"Microled site in Neurolight probe with id {id}",
                device=neurolight_probe,
                description=site_description,
                excitation_lambda=460.0,  # nm
                location=location,  # TODO find the mapping for precise location per site if possible
            )
            micro_led_ids_to_site[id] = optogenetic_site
            nwbfile.add_ogen_site(optogenetic_site)

        # Create the stimulus series
        for id in micro_led_ids:
            site_intervals = pulse_intervals[pulse_micro_led == id]
            site_amplitudes = pulse_amplitude[pulse_micro_led == id]
            pulse_start_time, pulse_stop_time = site_intervals[:, 0], site_intervals[:, 1]
            amplitude_at_start = np.zeros_like(pulse_start_time)
            amplitude_at_stop = site_amplitudes

            raise_time = 0.001  # 1 ms
            rise_to_max_time = pulse_start_time + raise_time
            amplitude_at_max = site_amplitudes

            # Assume from the trapezoidal profile that the decay time is the same as the rise time
            decay_time = pulse_stop_time + raise_time
            amplitude_after_decay = np.zeros_like(decay_time)

            timestamps = np.vstack((pulse_start_time, rise_to_max_time, pulse_stop_time, decay_time))
            data = np.vstack((amplitude_at_start, amplitude_at_max, amplitude_at_stop, amplitude_after_decay))

            site_timestamps = timestamps.T.flatten()
            site_data = data.T.flatten()

            optogenetic_series_description = (
                "μLEDs were controlled with current (2-4.5 μA generating 0.02-0.1μW of total light power;"
                "ref (15)) provided by a 12-channel current generator (OSC1Lite, NeuroNex Michigan Hub)"
                "driven by an Arduino, which delivered trapezoid (1ms rise time)"
                "blue light (centered emission at 460 nm, emission surface area = 150 mm2) 20 ms pulses at"
                "random sites with a randomly variable (40-60ms) offset"
            )
            optogenetic_site = micro_led_ids_to_site[id]
            optogenetic_series = OptogeneticSeries(
                name=f"Stimuli from microLED site {id}",
                timestamps=site_timestamps,
                data=site_data,
                site=optogenetic_site,
                description=optogenetic_series_description,
            )

            nwbfile.add_stimulus(optogenetic_series)


# class ValeroLaserPulsesInterface(BaseDataInterface):
#     def __init__(self, folder_path: FolderPathType):
#         super().__init__(folder_path=folder_path)

#     def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
#         self.session_path = Path(self.source_data["folder_path"])
#         self.session_id = self.session_path.stem

#         pulses_data_path = self.session_path / f"{self.session_id}.pulses.events.mat"
#         assert pulses_data_path.is_file(), f"{pulses_data_path} not found"

#         mat_file = read_mat(pulses_data_path)
#         pulses_data = mat_file["pulses"]

#         pulse_intervals = pulses_data["timestamps"]
#         electrode_channel = pulses_data["analogChannel"]
#         amplitude = pulses_data["amplitude"]

#         current = "2-4.5 μA"
#         light_power = "0.02-0.1μW"
#         reference = "(15)"
#         generator = "OSC1Lite, NeuroNex Michigan Hub"
#         arduino_link = "https://github.com/valegarman"
#         rise_time = "1ms"
#         light_type = "blue light"
#         emission = "460 nm"
#         area = "150 mm2"
#         pulse_duration = "20 ms"
#         offset = "40-60ms"

#         laser_description = f"""
#         μLEDs were controlled with current ({current} generating {light_power} of total light power;
#         ref {reference}) provided by a 12-channel current generator ({generator})
#         driven by an Arduino ({arduino_link}), which delivered trapezoid ({rise_time} rise time)
#         {light_type} (centered emission at {emission}, emission surface area = {area}) {pulse_duration} pulses at
#         random sites with a randomly variable ({offset}) offset.
#         """

#         stimuli_laser_pulses = TimeIntervals(
#             name="stimuli_laser_pulses",
#             description=laser_description,
#         )

#         stimuli_laser_pulses.add_column(name="electrode_channel", description="The electrode channel for the pulse")
#         stimuli_laser_pulses.add_column(name="amplitude", description="The amplitude of the pulse")

#         for interval, channel, amp in zip(pulse_intervals, electrode_channel, amplitude):
#             start_time, stop_time = interval
#             channel = channel
#             row_dict = dict(start_time=start_time, stop_time=stop_time, electrode_channel=channel, amplitude=amp)
#             stimuli_laser_pulses.add_row(**row_dict)

#         nwbfile.add_time_intervals(stimuli_laser_pulses)