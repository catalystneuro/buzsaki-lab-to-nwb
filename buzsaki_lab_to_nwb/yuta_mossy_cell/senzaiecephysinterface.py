"""Electrodes, LFP, wide-band signal and auxiliary inputs of a Senzai session (DANDI:000003)."""

from pathlib import Path
from typing import Optional, Union

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile, TimeSeries
from pynwb.ecephys import LFP, ElectricalSeries

from .senzaiutils import open_published, read_session_xml

# The paper's Amplipex system: 10 V range over 16 bits at x400 gain. The .xml files give 20 V and x1000, which look
# like template defaults: with 0.3815 uV per step, the faintest DS2 events in the LFP sit at the paper's 1.14 mV
# detection threshold, while the .xml value or the Intan value used earlier would put them well below it.
VOLTS_PER_STEP = 10 / 2**16 / 400

# Auxiliary inputs written in the earlier DANDI files, with the inputs the experiment sheets give for their channels
# in the 80-channel recordings (64 probe channels and 16 inputs). The earlier conversion read these channel numbers in
# every recording
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
N_CHANNELS_OF_AUXILIARY_TABLE = 80
# The experiment sheet of YutaMouse33 has a second list of inputs for part of one day
AUXILIARY_NOTES = {
    "YutaMouse33-150223": (
        "; the experiment sheet has a second list of the inputs for this day ('150223session9,10', 'switch "
        "865min28s'), in which each input is one channel higher and the wait area period is not listed"
    )
}


def auxiliary_channel(base_channel: int, n_recorded_channels: int):
    """The channel of an auxiliary input in a recording, or None when the recording has no such inputs.

    The inputs are the last 16 channels: 64 to 79 of the 80-channel recordings, 96 to 111 of the 112-channel
    recordings of YutaMouse33 (as its experiment sheet lists them, 32 channels up). The 65-channel recordings of
    YutaMouse20 and YutaMouse23 have none.
    """
    channel = base_channel + n_recorded_channels - N_CHANNELS_OF_AUXILIARY_TABLE
    return channel if n_recorded_channels >= N_CHANNELS_OF_AUXILIARY_TABLE and channel < n_recorded_channels else None


STUB_SAMPLES = 75_000
# Recording sites per shank of the two shank probes (the paper's Table S1)
SITES_PER_SHANK = {"Buzsaki64": 8, "Buzsaki64sp": 10}


def auxiliary_description(name: str, n_recorded_channels: int, session_id: str, share_file_name: str = None) -> str:
    """Description of an auxiliary input series; `share_file_name` is the lab's .eeg file when the series is read
    from it."""
    base_channel, what = AUXILIARY_CHANNELS[name]
    return (
        f"auxiliary input on channel {auxiliary_channel(base_channel, n_recorded_channels)} of the recording system: "
        f"{what}, in the system's raw int16 steps (the scaling of these inputs is not documented)"
        + (f", from the lab's {share_file_name}" if share_file_name else "")
        + AUXILIARY_NOTES.get(session_id, "")
    )


def group_kinds(group_sizes: list, sites_per_shank: int) -> list:
    """What each spike-detection channel group of the .xml file is: a "shank" of the shank probe, half of the 32-site
    "linear" probe (groups of 16 channels, in the YutaMouse33 sessions), or "other" channels."""
    return ["shank" if size == sites_per_shank else "linear" if size == 16 else "other" for size in group_sizes]


class SenzaiEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml file; LFP, wide-band signal and auxiliary inputs from its earlier DANDI file.

    The lab's .dat files and most .eeg files are not on the public share, so the signals are taken from the session's
    file in an earlier version of DANDI:000003. The columns of the 2021 files are the recording channels 0 to n-1 in
    order (checked against the .eeg files the share does have); the one 2019 file names each column's channel. Where
    the earlier file lacks probe channels or auxiliary inputs and the share has the session's .eeg file, they come
    from that file.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        published_nwb_file_path: Optional[Union[FilePath, str]] = None,  # a path, or a URL to stream
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
        sites_per_shank = SITES_PER_SHANK[probe]
        group_sizes = [len(channels) for channels in self.xml_info["shank_channels"]]
        kinds = group_kinds(group_sizes, sites_per_shank)
        n_shanks = kinds.count("shank")
        probe_device = nwbfile.create_device(
            name="probe",
            description=(
                f"NeuroNexus silicon probe ({probe}): {n_shanks} shanks 200 um apart, each with {sites_per_shank} "
                "staggered recording sites 20 um apart vertically"
                + (
                    "; the lab's .xml file also lists channel groups that are not shanks of this probe ("
                    + ", ".join(
                        f"group {index + 1} with {size} channel{'s' if size > 1 else ''}"
                        for index, (size, kind) in enumerate(zip(group_sizes, kinds))
                        if kind == "other"
                    )
                    + ")"
                    if "other" in kinds
                    else ""
                )
            ),
            manufacturer="NeuroNexus",
        )
        linear_device = None
        if "linear" in kinds:
            linear_device = nwbfile.create_device(
                name="linear_probe",
                description=(
                    "32-site linear silicon probe implanted in addition to the shank probe (the experiment sheet lists "
                    "a '32ch (linear probe)' and its channels in two columns of 16, 'top' and 'bottom', which are "
                    "channel groups "
                    + " and ".join(str(index + 1) for index, kind in enumerate(kinds) if kind == "linear")
                    + " of the lab's .xml file); the sheet gives no site spacing or separate location for it, and its "
                    "units are not in the lab's unit summary"
                ),
            )
        linear_halves = iter(("top", "bottom"))
        for group_index, (size, kind) in enumerate(zip(group_sizes, kinds)):
            name = f"shank{group_index + 1}"
            if kind == "shank":
                description = f"{name} of the probe, in the dentate gyrus and CA3 of the dorsal hippocampus"
            elif kind == "linear":
                description = (
                    f"channel group {group_index + 1} of the lab's .xml file: the 16 sites of the 32-site linear probe "
                    f"that the experiment sheet lists as '{next(linear_halves, 'further')}', in the sheet's order; "
                    "not a shank of the shank probe"
                )
            else:
                description = (
                    f"channel group {group_index + 1} of the lab's .xml file: {size} channel{'s' if size > 1 else ''} "
                    f"of the recording that {'are' if size > 1 else 'is'} not on a {sites_per_shank}-site shank of the "
                    "probe"
                )
            nwbfile.create_electrode_group(
                name=name,
                description=description,
                location="Hippocampal region",
                device=linear_device if kind == "linear" else probe_device,
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

    def read_share_signal(self, published_lfp, published_channels, stub_test: bool = False):
        """Every recorded channel of the lab's .eeg file, when the share has it and it holds the earlier file's LFP.

        The file is used when the channels the earlier DANDI file holds equal that file's LFP over the first 2^16
        samples and it has as many samples (a stub conversion may use the start of the file). The share's .lfp files
        are later exports that differ from the earlier files' LFP, so they are not read.
        """
        self.share_signal_file = self.session_path / f"{self.session_id}.eeg"
        n_recorded = self.xml_info["n_channels"]
        if not self.share_signal_file.is_file() or self.share_signal_file.stat().st_size % (2 * n_recorded):
            return None
        signal = np.memmap(self.share_signal_file, dtype=np.int16, mode="r").reshape(-1, n_recorded)
        n_published_samples = published_lfp.shape[0]
        if len(signal) != n_published_samples and not (stub_test and len(signal) >= STUB_SAMPLES):
            return None
        n_checked = min(len(signal), n_published_samples, 2**16)
        if not np.array_equal(signal[:n_checked][:, list(published_channels)], published_lfp[:n_checked]):
            return None
        return signal

    @staticmethod
    def published_lfp_channels(published, n_columns: int) -> list:
        """The recording channel of each LFP column of the earlier DANDI file.

        The 2021 files hold channels 0 to n-1 in order. The one 2019 file (YutaMouse33-150218) holds them in the
        order of the shanks' channel lists and names each column's channel in the amp_channel column of its
        electrodes table.
        """
        electrodes = published["general/extracellular_ephys/electrodes"]
        if "amp_channel" in electrodes and len(electrodes["amp_channel"]) == n_columns:
            return [int(channel) for channel in electrodes["amp_channel"][:]]
        return list(range(n_columns))

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is None:
            return
        # Kept open until the new file has been written
        self._published_file = published = open_published(published_nwb_file_path)
        if not np.array_equal(self.channels, np.arange(len(self.channels))):
            raise ValueError(
                f"The shank channels of {self.session_id} are not 0 to n-1, so the published columns cannot be mapped"
            )
        all_electrodes = nwbfile.create_electrode_table_region(
            region=list(range(len(self.channels))), description="all probe electrodes"
        )

        def electrodes_of(data):
            """Electrodes of the columns: channels 0 to n-1, which must be whole shanks."""
            n_columns = data.shape[1]
            if n_columns == len(self.channels):
                return all_electrodes, ""
            covered = set(range(n_columns))
            whole_shanks = all(
                set(group) <= covered or not set(group) & covered for group in self.xml_info["shank_channels"]
            )
            if n_columns > len(self.channels) or not whole_shanks:
                raise ValueError(f"{data.name} has {n_columns} columns for {len(self.channels)} probe channels")
            region = nwbfile.create_electrode_table_region(
                region=list(range(n_columns)), description=f"channels 0 to {n_columns - 1}"
            )
            return (
                region,
                f"; the earlier DANDI file holds only channels 0 to {n_columns - 1}, the first probe's shanks",
            )

        def select(data):
            return data[:STUB_SAMPLES] if stub_test else data

        lfp_group = published["processing/ecephys/LFP"]
        lfp = lfp_group["LFP"] if "LFP" in lfp_group else lfp_group["lfp"]
        lfp_data = lfp["data"]
        published_channels = self.published_lfp_channels(published, lfp_data.shape[1])
        share_signal = self.read_share_signal(lfp_data, published_channels, stub_test)
        if share_signal is not None and lfp_data.shape[1] < len(self.channels):
            n_published = lfp_data.shape[1]
            lfp_data, lfp_electrodes = share_signal[:, : len(self.channels)], all_electrodes
            lfp_note = (
                f"; from the lab's {self.share_signal_file.name}, because the earlier DANDI file holds the LFP of "
                f"{n_published} of the {len(self.channels)} probe channels only (those {n_published} are the same in both)"
            )
        elif published_channels != list(range(lfp_data.shape[1])):
            # Columns in another order than the channel numbers: each column refers to its own channel's electrode
            rows = [int(np.flatnonzero(self.channels == channel)[0]) for channel in published_channels]
            lfp_electrodes = nwbfile.create_electrode_table_region(
                region=rows, description="the channel of each column, from the earlier DANDI file's amp_channel"
            )
            lfp_note = (
                "; the columns are in the order of the earlier DANDI file, which is not the order of the channel "
                "numbers and does not hold every probe channel"
                if len(rows) < len(self.channels)
                else "; the columns are in the order of the earlier DANDI file, which is not the order of the channel numbers"
            )
        else:
            lfp_electrodes, lfp_note = electrodes_of(lfp_data)
        lfp_series = ElectricalSeries(
            name="lfp",
            description="LFP of the probe channels: the wide-band signal down-sampled to 1250 Hz by the lab" + lfp_note,
            data=SliceableDataChunkIterator(data=select(lfp_data)),
            electrodes=lfp_electrodes,
            rate=float(lfp["starting_time"].attrs["rate"]),
            conversion=VOLTS_PER_STEP,
        )
        ecephys_module = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")
        ecephys_module.add(LFP(electrical_series=lfp_series))

        # The earlier DANDI files of 41 sessions also held the theta and gamma phase of a hilus LFP channel. It was
        # computed by that conversion, not by the lab, and is not carried over.

        if "acquisition/ElectricalSeries" in published:
            wideband = published["acquisition/ElectricalSeries"]
            wideband_electrodes, wideband_note = electrodes_of(wideband["data"])
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description="wide-band signal of the probe channels, recorded at 20 kHz on an Amplipex system"
                    + wideband_note,
                    data=SliceableDataChunkIterator(data=select(wideband["data"])),
                    electrodes=wideband_electrodes,
                    rate=float(wideband["starting_time"].attrs["rate"]),
                    conversion=VOLTS_PER_STEP,
                )
            )

        n_recorded = self.xml_info["n_channels"]
        for name, (base_channel, description) in AUXILIARY_CHANNELS.items():
            channel = auxiliary_channel(base_channel, n_recorded)
            if channel is None:
                continue
            if n_recorded == N_CHANNELS_OF_AUXILIARY_TABLE:
                # The earlier file's series are these channels
                if f"acquisition/{name}" not in published:
                    continue
                data = published[f"acquisition/{name}/data"]
                data = data[:STUB_SAMPLES] if stub_test else data[:]
                rate = float(published[f"acquisition/{name}/starting_time"].attrs["rate"])
                source = None
            elif share_signal is not None:
                # In other recordings the earlier file's series are probe channels (it read the same channel numbers
                # in every recording), so the inputs come from the lab's .eeg file
                data = np.asarray(share_signal[:STUB_SAMPLES, channel] if stub_test else share_signal[:, channel])
                rate = self.xml_info["lfp_sampling_rate"]
                source = self.share_signal_file.name
            else:
                continue
            nwbfile.add_acquisition(
                TimeSeries(
                    name=name,
                    description=auxiliary_description(name, n_recorded, self.session_id, source),
                    data=data,
                    unit="a.u.",
                    rate=rate,
                )
            )
