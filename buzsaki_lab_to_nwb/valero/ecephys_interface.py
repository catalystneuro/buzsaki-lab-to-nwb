"""Electrodes, LFP and wide-band signal of a Valero session (DANDI:000568)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .valeroutils import electrode_groups, read_session

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


class ValeroEcephysInterface(BaseDataInterface):
    """Electrodes from session.mat and chanCoords; LFP from the .lfp file and wide-band signal from the .dat file.

    The .lfp and .dat files are int16, interleaved by channel, with session.mat giving 0.195 uV per step
    (extracellular.leastSignificantBit, the Intan RHD2000 step).
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.session = read_session(self.session_path)
        extracellular = self.session["extracellular"]
        self.n_channels = int(extracellular["nChannels"])
        self.sampling_rate = float(extracellular["sr"])
        self.lfp_sampling_rate = float(extracellular["srLfp"])
        self.volts_per_step = float(extracellular["leastSignificantBit"]) * 1e-6
        self.shank_channels = electrode_groups(self.session)

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

    def _memmap(self, suffix: str):
        file_path = self.session_path / f"{self.session_id}{suffix}"
        if not file_path.is_file():
            return None
        return np.memmap(file_path, dtype=np.int16, mode="r").reshape(-1, self.n_channels)

    def add_to_nwbfile(
        self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, write_lfp: bool = True, write_raw: bool = True
    ):
        self.add_electrodes(nwbfile)
        electrodes = nwbfile.create_electrode_table_region(
            region=list(range(self.n_channels)), description="all probe channels"
        )
        step = f"{self.volts_per_step * 1e6:g} uV per step (session.mat extracellular.leastSignificantBit)"
        lfp = self._memmap(".lfp") if write_lfp else None
        if lfp is not None:
            series = ElectricalSeries(
                name="ElectricalSeriesLFP",
                description=f"LFP of the probe channels from the lab's .lfp file (wide-band signal down-sampled to "
                f"{self.lfp_sampling_rate:g} Hz), int16 steps of {step}",
                data=SliceableDataChunkIterator(data=lfp[:STUB_SAMPLES] if stub_test else lfp),
                electrodes=electrodes,
                rate=self.lfp_sampling_rate,
                conversion=self.volts_per_step,
            )
            get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
                LFP(electrical_series=series)
            )
        raw = self._memmap(".dat") if write_raw else None
        if raw is not None:
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description=f"wide-band signal of the probe channels from the lab's .dat file, recorded at "
                    f"{self.sampling_rate:g} Hz with an Intan RHD2000 system, int16 steps of {step}",
                    data=SliceableDataChunkIterator(data=raw[:STUB_SAMPLES] if stub_test else raw),
                    electrodes=electrodes,
                    rate=self.sampling_rate,
                    conversion=self.volts_per_step,
                )
            )
