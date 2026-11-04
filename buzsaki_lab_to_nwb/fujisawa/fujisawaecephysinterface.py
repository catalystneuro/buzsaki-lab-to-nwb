"""Electrodes, LFP and wide-band signal of a Fujisawa session (DANDI:000067)."""

from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from lxml import etree
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .fujisawautils import AUXILIARY_CHANNELS, read_channel_groups, region_of_shank, subject_of

STUB_SAMPLES = 75_000
LOCATIONS = {"mPFC": "medial prefrontal cortex", "CA1": "CA1 field of hippocampus", "none": "none"}


def volts_per_step(xml_file_path: Path) -> float:
    """The scaling of the .xml file: voltage range over 2^nBits at the amplification.

    The recording system and its gain are not documented elsewhere in the source or the CRCNS description.
    """
    acquisition = etree.parse(str(xml_file_path)).getroot().find("acquisitionSystem")
    voltage_range = float(acquisition.find("voltageRange").text)
    n_bits = int(acquisition.find("nBits").text)
    amplification = float(acquisition.find("amplification").text)
    return voltage_range / 2**n_bits / amplification


class FujisawaEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml file and the CRCNS channel map; LFP and wide-band signal from the session's
    earlier DANDI file, or the wide-band signal from the lab's .dat file for sessions that have no earlier file.

    The LFP and wide-band series hold every channel of the recording, the 13th channel group being the non-neural
    inputs (nose-poke sensors, wheel encoders, sync), which are in the electrodes table with location 'none'.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        published_nwb_file_path: Optional[FilePath] = None,
        dat_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            published_nwb_file_path=published_nwb_file_path,
            dat_file_path=dat_file_path,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.subject = subject_of(self.session_id)
        xml_file_path = next(
            path
            for path in (self.session_path / f"{self.session_id}.xml", self.session_path / f"{self.subject}.xml")
            if path.is_file()
        )
        self.channel_groups = read_channel_groups(xml_file_path)
        self.conversion = volts_per_step(xml_file_path)

    def add_electrodes(self, nwbfile: NWBFile):
        probes = dict(
            mPFC=nwbfile.create_device(
                name="Buzsaki64",
                description=(
                    "NeuroNexus Buzsaki64 silicon probe in the medial prefrontal cortex (layer 2/3 or 5; AP 3.0 to "
                    "4.4 mm, ML 0.5 mm): 8 shanks 200 um apart, each with 8 staggered recording sites (160 um2, "
                    "1 to 3 MOhm) 20 um apart vertically"
                ),
                manufacturer="NeuroNexus",
            ),
            CA1=nwbfile.create_device(
                name="Buzsaki32",
                description="NeuroNexus Buzsaki32 silicon probe in the intermediate CA1: 4 shanks of 8 recording sites",
                manufacturer="NeuroNexus",
            ),
        )
        auxiliary = AUXILIARY_CHANNELS[self.subject]
        nwbfile.add_electrode_column(name="channel_id", description="1-based channel number of the recording")
        nwbfile.add_electrode_column(
            name="signal", description="what the channel records: 'neural', or the non-neural input on the channel"
        )
        channel_to_group = {}
        for index, channels in enumerate(self.channel_groups["groups"]):
            shank = index + 1
            region = region_of_shank(shank)
            if region == "none":
                group = nwbfile.create_electrode_group(
                    name="auxiliary",
                    description="the non-neural inputs of the recording system: nose-poke sensors, wheel encoders, sync",
                    location="none",
                    device=nwbfile.create_device(name="auxiliary inputs", description="non-neural inputs"),
                )
            else:
                group = nwbfile.create_electrode_group(
                    name=f"shank{shank}",
                    description=f"shank {shank} of the {probes[region].name} probe ({LOCATIONS[region]})",
                    location=LOCATIONS[region],
                    device=probes[region],
                )
            for channel in channels:
                channel_to_group[channel] = group
        for channel in range(self.channel_groups["n_channels"]):
            group = channel_to_group.get(channel)
            if group is None:
                raise ValueError(f"Channel {channel + 1} of {self.session_id} is in no channel group of its .xml")
            is_auxiliary = group.name == "auxiliary"
            nwbfile.add_electrode(
                group=group,
                group_name=group.name,
                location=group.location,
                channel_id=channel + 1,
                signal=auxiliary.get(channel + 1, "not documented") if is_auxiliary else "neural",
            )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        n_channels = self.channel_groups["n_channels"]
        all_channels = nwbfile.create_electrode_table_region(
            region=list(range(n_channels)), description="all channels of the recording"
        )
        scaling = (
            f"; scaled to volts with the .xml file's {self.conversion * 1e6:.4g} uV per step (the recording system's "
            "gain is not documented elsewhere)"
        )

        def select(data):
            return data[:STUB_SAMPLES] if stub_test else data

        def check_columns(data):
            if data.shape[1] != n_channels:
                raise ValueError(f"{data.name} has {data.shape[1]} columns for {n_channels} channels")

        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is not None:
            # Kept open until the new file has been written
            self._published_file = published = h5py.File(published_nwb_file_path, "r")
            lfp = published["processing/ecephys/LFP/LFP"]
            check_columns(lfp["data"])
            lfp_series = ElectricalSeries(
                name="LFP",
                description="the wide-band signal low-pass filtered and down-sampled to 1250 Hz by the lab (.eeg file)"
                + scaling,
                data=SliceableDataChunkIterator(data=select(lfp["data"])),
                electrodes=all_channels,
                rate=float(lfp["starting_time"].attrs["rate"]),
                conversion=self.conversion,
            )
            get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
                LFP(electrical_series=lfp_series)
            )
            if "acquisition/ElectricalSeries" in published:
                wideband = published["acquisition/ElectricalSeries"]
                check_columns(wideband["data"])
                wideband_data, wideband_rate = wideband["data"], float(wideband["starting_time"].attrs["rate"])
            else:
                wideband_data = None
        elif self.source_data["dat_file_path"] is not None:
            wideband_data = np.memmap(self.source_data["dat_file_path"], dtype=np.int16, mode="r").reshape(
                -1, n_channels
            )
            wideband_rate = 20_000.0
        else:
            wideband_data = None

        if wideband_data is not None:
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description="wide-band signal of all channels, recorded at 20 kHz (.dat file)" + scaling,
                    data=SliceableDataChunkIterator(data=select(wideband_data)),
                    electrodes=all_channels,
                    rate=wideband_rate,
                    conversion=self.conversion,
                )
            )
