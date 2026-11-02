"""Electrodes, LFP, wide-band signal and auxiliary inputs of a Senzai session (DANDI:000003)."""

from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile, TimeSeries
from pynwb.ecephys import LFP, ElectricalSeries

from .senzaiutils import read_session_xml

# The paper's Amplipex system: 10 V range over 16 bits at x400 gain. The .xml files give 20 V and x1000, which look
# like template defaults: with 0.3815 uV per step, the faintest DS2 events in the LFP sit at the paper's 1.14 mV
# detection threshold, while the .xml value or the Intan value used earlier would put them well below it.
VOLTS_PER_STEP = 10 / 2**16 / 400

# Auxiliary inputs written in the earlier DANDI files, with the inputs the experiment sheets give for their channels
AUXILIARY_CHANNELS = {
    "ch_dig1": (65, "TDT digital output 1"),
    "ch_dig2": (68, "TDT digital output 2"),
    "ch_SsolR": (70, "sensor 1, right side arm"),
    "ch_entR": (71, "sensor 2, right entrance to the wait area"),
    "ch_entL": (72, "sensor 3, left entrance to the wait area"),
    "ch_SsolL": (73, "sensor 4, left side arm"),
    "ch_solL": (76, "solenoid 1 (left water port)"),
    "ch_solR": (77, "solenoid 2 (right water port)"),
    "ch_arm": (78, "central arm period"),
    "ch_wait": (79, "wait area period"),
}
STUB_SAMPLES = 75_000


class SenzaiEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml file; LFP, wide-band signal and auxiliary inputs from its earlier DANDI file.

    The lab's .eeg and .dat files are not on the public share, so the signals are taken from the session's file in
    an earlier version of DANDI:000003, whose columns are the recording channels 0 to n-1 in order. Only the
    electrodes table of those files was wrong.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        published_nwb_file_path: Optional[FilePath] = None,
        hilus_channel: Optional[int] = None,
        probe: Optional[str] = None,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            published_nwb_file_path=published_nwb_file_path,
            hilus_channel=hilus_channel,
            probe=probe,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.channels = np.sort(np.concatenate(self.xml_info["shank_channels"]))

    def add_electrodes(self, nwbfile: NWBFile):
        probe = self.source_data["probe"]
        n_shanks = len(self.xml_info["shank_channels"])
        device = nwbfile.create_device(
            name="probe",
            description=(
                f"NeuroNexus silicon probe ({probe}): {n_shanks} shanks 200 um apart, with staggered recording sites "
                "20 um apart vertically (8 sites per shank on Buzsaki64, 10 on Buzsaki64sp)"
            ),
            manufacturer="NeuroNexus",
        )
        for shank_index, _ in enumerate(self.xml_info["shank_channels"]):
            name = f"shank{shank_index + 1}"
            nwbfile.create_electrode_group(
                name=name,
                description=f"{name} of the probe, in the dentate gyrus and CA3 of the dorsal hippocampus",
                location="Hippocampal region",
                device=device,
            )

        channel_to_shank = {
            channel: (shank_index, site)
            for shank_index, channels in enumerate(self.xml_info["shank_channels"])
            for site, channel in enumerate(channels)
        }
        nwbfile.add_electrode_column(
            name="channel_id", description="channel number in the lab's .xml, .dat and .eeg files"
        )
        nwbfile.add_electrode_column(
            name="shank_electrode_number",
            description="0-indexed position of the channel in its shank's channel list in the .xml file",
        )
        nwbfile.add_electrode_column(
            name="hilus_reference",
            description="the hilus channel the lab used for dentate spikes and for theta and gamma phase",
        )
        for channel in self.channels:
            shank_index, site = channel_to_shank[channel]
            group = nwbfile.electrode_groups[f"shank{shank_index + 1}"]
            nwbfile.add_electrode(
                group=group,
                group_name=group.name,
                location=group.location,
                channel_id=int(channel),
                shank_electrode_number=site,
                hilus_reference=bool(channel == self.source_data["hilus_channel"]),
            )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is None:
            return
        # Kept open until the new file has been written
        self._published_file = published = h5py.File(published_nwb_file_path, "r")
        if not np.array_equal(self.channels, np.arange(len(self.channels))):
            raise ValueError(
                f"The shank channels of {self.session_id} are not 0 to n-1, so the published columns cannot be mapped"
            )
        all_electrodes = nwbfile.create_electrode_table_region(
            region=list(range(len(self.channels))), description="all probe electrodes"
        )

        def select(data):
            if data.shape[1] != len(self.channels):
                raise ValueError(f"{data.name} has {data.shape[1]} columns for {len(self.channels)} probe channels")
            return data[:STUB_SAMPLES] if stub_test else data

        lfp = published["processing/ecephys/LFP/LFP"]
        lfp_series = ElectricalSeries(
            name="lfp",
            description="LFP of all probe channels: the wide-band signal down-sampled to 1250 Hz by the lab",
            data=SliceableDataChunkIterator(data=select(lfp["data"])),
            electrodes=all_electrodes,
            rate=float(lfp["starting_time"].attrs["rate"]),
            conversion=VOLTS_PER_STEP,
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
            LFP(electrical_series=lfp_series)
        )

        if "acquisition/ElectricalSeries" in published:
            wideband = published["acquisition/ElectricalSeries"]
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description="wide-band signal of all probe channels, recorded at 20 kHz on an Amplipex system",
                    data=SliceableDataChunkIterator(data=select(wideband["data"])),
                    electrodes=all_electrodes,
                    rate=float(wideband["starting_time"].attrs["rate"]),
                    conversion=VOLTS_PER_STEP,
                )
            )

        for name, (channel, description) in AUXILIARY_CHANNELS.items():
            if f"acquisition/{name}" not in published:
                continue
            data = published[f"acquisition/{name}/data"]
            nwbfile.add_acquisition(
                TimeSeries(
                    name=name,
                    description=(
                        f"auxiliary input on channel {channel} of the recording system: {description}, "
                        "in the system's raw int16 steps (the scaling of these inputs is not documented)"
                    ),
                    data=data[:STUB_SAMPLES] if stub_test else data[:],
                    unit="a.u.",
                    rate=float(published[f"acquisition/{name}/starting_time"].attrs["rate"]),
                )
            )
