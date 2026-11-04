"""Electrodes, LFP and wide-band signal of a Valero session (DANDI:000568)."""

from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .valeroutils import as_list, electrode_groups, read_session

STUB_SAMPLES = 100_000
LOCATION = "CA1"


def generate_neurolight_device_metadata() -> dict:
    return dict(
        name="N1-F21-O36 | 18",
        manufacturer="Neurolight Technologies",
        description=(
            "uLED silicon probe: 4 shanks, 8 recording channels and 3 uLEDs (10 x 15 um each, emission area "
            "150 um2) per shank; emission peak 460 nm, FWHM 40 nm; typical irradiance of 33 mW/mm2 at the maximum "
            "operating current of 100 uA; electrode impedance 1000-1500 kOhm at 1 kHz. Implanted over the dorsal "
            "right hippocampus (antero-posterior 2.0 mm, mediolateral 1.5 mm, dorsoventral 0.6 mm) and advanced to "
            "the CA1 pyramidal layer."
        ),
    )


def get_neurolight_device(nwbfile: NWBFile):
    metadata = generate_neurolight_device_metadata()
    if metadata["name"] not in nwbfile.devices:
        nwbfile.create_device(**metadata)
    return nwbfile.devices[metadata["name"]]


def read_xml_channels(xml_path: Path) -> tuple:
    """(number of channels, sampling rate, LFP sampling rate) from the lab's .xml file."""
    root = ElementTree.parse(xml_path).getroot()
    acquisition = root.find("acquisitionSystem")
    n_channels = int(acquisition.find("nChannels").text)
    sampling_rate = float(acquisition.find("samplingRate").text)
    lfp_rate = root.find("fieldPotentials/lfpSamplingRate")
    return n_channels, sampling_rate, float(lfp_rate.text) if lfp_rate is not None else None


class ValeroEcephysInterface(BaseDataInterface):
    """Electrodes from session.mat and chanCoords; LFP from the .lfp file and wide-band signal from the .dat file.

    The .lfp and .dat files are int16, interleaved by channel, with session.mat giving 0.195 uV per step
    (extracellular.leastSignificantBit, the Intan RHD2000 step). They are read from the session folder or, when it
    lacks them, from `signals_folder_path` (a folder with <session>.lfp and <session>.dat from another copy of the
    lab's data, such as the 2023 source copy); a file from there must match the session's channel count and timing.
    """

    # Largest difference (s) allowed between a signal file's duration and the session's other timing
    DURATION_TOLERANCE = 1.0

    def __init__(
        self, folder_path: DirectoryPath, signals_folder_path: Optional[DirectoryPath] = None, verbose: bool = False
    ):
        super().__init__(folder_path=folder_path, signals_folder_path=signals_folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.signals_path = Path(signals_folder_path) if signals_folder_path else None
        self.session_id = self.session_path.name
        self.session = read_session(self.session_path)
        extracellular = self.session["extracellular"]
        self.n_channels = int(extracellular["nChannels"])
        self.sampling_rate = float(extracellular["sr"])
        self.lfp_sampling_rate = float(extracellular["srLfp"])
        self.volts_per_step = float(extracellular["leastSignificantBit"]) * 1e-6
        self.shank_channels = electrode_groups(self.session)
        xml_path = self.session_path / f"{self.session_id}.xml"
        if xml_path.is_file():
            xml_channels, xml_rate, xml_lfp_rate = read_xml_channels(xml_path)
            if (xml_channels, xml_rate) != (self.n_channels, self.sampling_rate) or xml_lfp_rate not in (
                None,
                self.lfp_sampling_rate,
            ):
                raise ValueError(
                    f"{xml_path.name} gives {xml_channels} channels at {xml_rate} Hz (LFP {xml_lfp_rate} Hz) and "
                    f"session.mat {self.n_channels} channels at {self.sampling_rate} Hz "
                    f"(LFP {self.lfp_sampling_rate} Hz)"
                )

    def session_timing(self) -> dict:
        """Durations (s) of the recording from the session's other files, to check the signal files against."""
        timing = {}
        epochs = as_list(self.session["epochs"])
        timing["end of the last epoch in session.mat"] = max(float(epoch["stopTime"]) for epoch in epochs)
        n_samples = self.session["extracellular"].get("nSamples")
        if np.size(n_samples) == 1 and np.isfinite(float(n_samples)) and float(n_samples) > 0:
            timing["session.mat extracellular.nSamples"] = float(n_samples) / self.sampling_rate
        merge_points = self.session_path / f"{self.session_id}.MergePoints.events.mat"
        if merge_points.is_file():
            stamps = read_mat(str(merge_points))["MergePoints"]["timestamps"]
            timing["end of the last sub-session in MergePoints"] = float(np.max(stamps))
        return timing

    def last_spike_time(self) -> Optional[float]:
        spikes_path = self.session_path / f"{self.session_id}.spikes.cellinfo.mat"
        if not spikes_path.is_file():
            return None
        times = read_mat(str(spikes_path), variable_names=["spikes"])["spikes"]["times"]
        return max(float(np.max(unit_times)) for unit_times in times if np.size(unit_times))

    def find_signal(self, suffix: str, rate: float):
        """(path, from the signals folder) of the session's .lfp or .dat file, checked against the session."""
        local = self.session_path / f"{self.session_id}{suffix}"
        if local.is_file():
            return local, False
        if self.signals_path is None:
            return None, False
        candidate = self.signals_path / f"{self.session_id}{suffix}"
        if not candidate.is_file():
            return None, False
        size = candidate.stat().st_size
        bytes_per_sample = 2 * self.n_channels
        if size % bytes_per_sample:
            raise ValueError(
                f"{candidate} has {size} bytes, not a whole number of int16 samples of {self.n_channels} channels "
                f"(the channel count of {self.session_id}.xml and session.mat), so it is not this recording"
            )
        duration = size / bytes_per_sample / rate
        problems = [
            f"{name} is {reference:.3f} s"
            for name, reference in self.session_timing().items()
            if abs(reference - duration) > self.DURATION_TOLERANCE
        ]
        last_spike = self.last_spike_time()
        if last_spike is not None and last_spike > duration:
            problems.append(f"the last spike is at {last_spike:.3f} s")
        if problems:
            raise ValueError(
                f"{candidate} lasts {duration:.3f} s at {rate:g} Hz and {self.n_channels} channels, but "
                + "; ".join(problems)
                + ", so it is not this recording"
            )
        return candidate, True

    def checked_durations(self, found: dict):
        """The .lfp and .dat in use must have the same duration."""
        durations = {
            suffix: path.stat().st_size / (2 * self.n_channels) / rate
            for suffix, (path, rate) in found.items()
            if path is not None
        }
        if len(durations) == 2 and abs(durations[".lfp"] - durations[".dat"]) > self.DURATION_TOLERANCE:
            raise ValueError(
                f"the .lfp lasts {durations['.lfp']:.3f} s and the .dat {durations['.dat']:.3f} s for {self.session_id}"
            )

    def add_electrodes(self, nwbfile: NWBFile):
        if len(nwbfile.electrode_groups):
            return
        device = get_neurolight_device(nwbfile)
        for index, _ in enumerate(self.shank_channels):
            nwbfile.create_electrode_group(
                name=f"shank{index + 1}",
                description=f"shank {index + 1} of the uLED probe (electrode group {index + 1} of session.mat)",
                location=LOCATION,
                device=device,
            )
        channel_to_shank = {
            int(channel): index for index, channels in enumerate(self.shank_channels) for channel in channels
        }
        coords_path = self.session_path / f"{self.session_id}.chanCoords.channelInfo.mat"
        coords = read_mat(str(coords_path))["chanCoords"] if coords_path.is_file() else None
        nwbfile.add_electrode_column(
            name="channel_id", description="0-indexed channel (column) of the .dat and .lfp files"
        )
        if coords is not None:
            for axis in ("x", "y"):
                nwbfile.add_electrode_column(
                    name=f"rel_{axis}", description=f"{axis} position of the site on the probe (um), from chanCoords"
                )
        for channel in range(self.n_channels):
            group = nwbfile.electrode_groups[f"shank{channel_to_shank[channel] + 1}"]
            extra = {}
            if coords is not None:
                extra = dict(rel_x=float(coords["x"][channel]), rel_y=float(coords["y"][channel]))
            nwbfile.add_electrode(group=group, group_name=group.name, location=LOCATION, channel_id=channel, **extra)

    def add_to_nwbfile(
        self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, write_lfp: bool = True, write_raw: bool = True
    ):
        self.add_electrodes(nwbfile)
        electrodes = nwbfile.create_electrode_table_region(
            region=list(range(self.n_channels)), description="all probe channels"
        )
        step = f"{self.volts_per_step * 1e6:g} uV per step (session.mat extracellular.leastSignificantBit)"
        lfp_path, lfp_external = self.find_signal(".lfp", self.lfp_sampling_rate) if write_lfp else (None, False)
        raw_path, raw_external = self.find_signal(".dat", self.sampling_rate) if write_raw else (None, False)
        self.checked_durations({".lfp": (lfp_path, self.lfp_sampling_rate), ".dat": (raw_path, self.sampling_rate)})

        def origin(external: bool) -> str:
            if not external:
                return ""
            return (
                "; the file is from the 2023 source copy of the lab's data (the copy converted in 2023), because the "
                "session folder used for everything else lacks it; it was checked to have this session's channel "
                "count and duration"
            )

        def memmap(path: Path):
            return np.memmap(path, dtype=np.int16, mode="r").reshape(-1, self.n_channels)

        if lfp_path is not None:
            lfp = memmap(lfp_path)
            series = ElectricalSeries(
                name="ElectricalSeriesLFP",
                description=f"LFP of the probe channels from the lab's .lfp file (wide-band signal down-sampled to "
                f"{self.lfp_sampling_rate:g} Hz), int16 steps of {step}" + origin(lfp_external),
                data=SliceableDataChunkIterator(data=lfp[:STUB_SAMPLES] if stub_test else lfp),
                electrodes=electrodes,
                rate=self.lfp_sampling_rate,
                conversion=self.volts_per_step,
            )
            get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
                LFP(electrical_series=series)
            )
        if raw_path is not None:
            raw = memmap(raw_path)
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description=f"wide-band signal of the probe channels from the lab's .dat file, recorded at "
                    f"{self.sampling_rate:g} Hz with an Intan RHD2000 system, int16 steps of {step}"
                    + origin(raw_external),
                    data=SliceableDataChunkIterator(data=raw[:STUB_SAMPLES] if stub_test else raw),
                    electrodes=electrodes,
                    rate=self.sampling_rate,
                    conversion=self.volts_per_step,
                )
            )
