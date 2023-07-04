from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile
from pynwb.ogen import OptogeneticSeries, OptogeneticStimulusSite

from buzsaki_lab_to_nwb.valero.ecephys_interface import (
    generate_neurolight_device_metadata,
)


class VeleroOptogeneticStimuliInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        pulses_data_path = self.session_path / f"{self.session_id}.pulses.events.mat"
        assert pulses_data_path.is_file(), f"{pulses_data_path} not found"

        ignore_fields = ["duration"]
        mat_file = read_mat(pulses_data_path, ignore_fields=ignore_fields)
        pulses_data = mat_file["pulses"]

        # Create device
        device_metadata = generate_neurolight_device_metadata()
        if device_metadata["name"] not in nwbfile.devices:
            neurolight_probe = nwbfile.create_device(**device_metadata)
        else:
            neurolight_probe = nwbfile.devices[device_metadata["name"]]

        site_identity_is_available = "analogueChannel" in pulses_data or "analogChannelsList" in pulses_data
        if site_identity_is_available:
            self.add_one_optogenetic_series_per_site(nwbfile, neurolight_probe, pulses_data)
        else:
            # Maybe we should a single optogenetic series for all sites
            return None

    def add_one_optogenetic_series_per_site(self, nwbfile: NWBFile, neurolight_probe, pulses_data):
        # Create the sites
        site_description = f"Microled site in Neurolight probe. Microscopic LED 10 x 15 µm each, 3 per shank. Each μLED has an emission area of 150 μm2"
        location = "dorsal right hippocampus (antero-posterior 2.0 mm, mediolateral 1.5 mm, dorsoventral 0.6 mm)"

        pulse_intervals = pulses_data["timestamps"]
        pulse_amplitude = pulses_data["amplitude"]
        pulse_micro_led = pulses_data.get("analogChannel", None)
        pulse_micro_led = pulses_data["analogChannelsList"] if pulse_micro_led is None else pulse_micro_led

        # Sometimes ()the last timestamps are cut off, e.g. `'fCamk1_200901_sess12'`, so we need to remove them
        # According to the paper the duration of the pulses is 20 ms (the data actually shows something like 19.6 ms)
        # The shorter pulses are probably due to the fact that the last pulses are cut off and writing their
        # timestamps as it is leads to a non-monothonic time series
        # We discard them using the heuristic that the last pulse should be at least 15 ms

        duration = pulses_data["duration"]
        good_data = duration > 0.015

        pulse_intervals = pulse_intervals[good_data]
        pulse_amplitude = pulse_amplitude[good_data]
        pulse_micro_led = pulse_micro_led[good_data]

        micro_led_ids = np.unique(pulse_micro_led)
        micro_led_ids_to_site = dict()

        for id in micro_led_ids:
            optogenetic_site = OptogeneticStimulusSite(
                name=f"OptogeneticStimulusSite{id}",
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

            # Assume from the trapezoidal profile that the decay time is the same as the rise time
            pulse_start_time = site_intervals[:, 0]
            amplitude_at_start = np.zeros_like(pulse_start_time)

            time_to_raise_to_max = 0.001  # 1 ms
            rise_to_max_time = pulse_start_time + time_to_raise_to_max
            amplitude_at_max = site_amplitudes

            pulse_stop_time = site_intervals[:, 1]
            start_decaying_time = pulse_stop_time - time_to_raise_to_max
            amplitude_start_decaying = site_amplitudes
            ampltidue_stop_time = np.zeros_like(start_decaying_time)

            timestamps = np.vstack((pulse_start_time, rise_to_max_time, start_decaying_time, pulse_stop_time))
            data = np.vstack((amplitude_at_start, amplitude_at_max, amplitude_start_decaying, ampltidue_stop_time))

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
                name=f"OptogeneticSeriesSite{id}",
                timestamps=site_timestamps,
                data=site_data,
                site=optogenetic_site,
                description=optogenetic_series_description,
            )

            nwbfile.add_stimulus(optogenetic_series)


class ValeroLaserPulsesInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        pulses_data_path = self.session_path / f"{self.session_id}.pulses.events.mat"
        assert pulses_data_path.is_file(), f"{pulses_data_path} not found"

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
