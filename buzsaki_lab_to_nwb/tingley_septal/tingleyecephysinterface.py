"""Electrodes, LFP and wide-band signal of a Tingley session (DANDI:000213, DANDI:000218)."""

from collections import Counter
from itertools import groupby
from pathlib import Path
from typing import Optional, Union

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .tingleyutils import REGION_NAMES, VOLTS_PER_STEP, read_event_files, read_session_info, read_session_xml

STUB_SAMPLES = 75_000
RECORDING_SYSTEM = (
    "Recorded with an Intan RHD2000 interface board at 20 kHz (amplification and digitization on the head stage, "
    "0.195 uV per step); grounded to two stainless steel screws above the cerebellum (Tingley and Buzsaki 2018)."
)


class PublishedColumns:
    """The columns of a published ElectricalSeries in the order of the new electrodes table, as int16 steps.

    The published files hold the lab's int16 .lfp/.dat values as float32; each block read is checked to be whole steps
    within the int16 range before it is cast back.
    """

    def __init__(self, dataset: h5py.Dataset, column_order: np.ndarray, n_samples: Optional[int] = None):
        self.dataset = dataset
        self.column_order = np.asarray(column_order)
        self.shape = (n_samples or dataset.shape[0], len(self.column_order))
        self.dtype = np.dtype("int16")
        self.ndim = 2

    def __getitem__(self, selection):
        rows, columns = selection if isinstance(selection, tuple) else (selection, slice(None))
        # Read only the range of published columns needed (a long session's block of all columns can need >100 GiB)
        wanted = np.atleast_1d(self.column_order[columns])
        first, last = int(wanted.min()), int(wanted.max())
        block = self.dataset[rows, first : last + 1][:, wanted - first]
        steps = np.rint(block)
        if not np.array_equal(steps, block) or steps.min(initial=0) < -(2**15) or steps.max(initial=0) >= 2**15:
            raise ValueError(f"{self.dataset.name} holds values that are not int16 steps")
        return steps.astype(np.int16)


class TingleyEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml and sessionInfo.mat files; the LFP and wide-band signal from the session's
    file in the earlier version of the dandiset, because the lab's .lfp and .dat files are not on the public share.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        published_nwb_file_path: Optional[Union[FilePath, str]] = None,  # a path, or a URL to stream
        include_wideband: bool = True,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            published_nwb_file_path=published_nwb_file_path,
            include_wideband=include_wideband,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.session_info = read_session_info(self.session_path, self.session_id)
        self.n_channels = self.xml_info["n_channels"]
        channels = [channel for group in self.xml_info["shank_channels"] for channel in group]
        if len(set(channels)) != len(channels) or not set(channels) <= set(range(self.n_channels)):
            raise ValueError(f"The spike groups of {self.session_id} hold a channel twice or a channel above n-1")
        # Channels in no spike group (in DT1: two unused probe channels and two above the probe's 32)
        self.ungrouped_channels = sorted(set(range(self.n_channels)) - set(channels))
        if self.session_info and self.session_info["region"]:
            labels = len(self.session_info["region"])
            # DT1: 32 labels for the probe's channels; the channels above them are in no spike group
            if labels > self.n_channels or any(channel not in self.ungrouped_channels for channel in range(labels, self.n_channels)):
                raise ValueError(f"sessionInfo.region of {self.session_id} does not have one label per channel")

    def channel_regions(self) -> list:
        """The lab's region label of each channel (sessionInfo.region), or 'unknown'."""
        if self.session_info and self.session_info["region"]:
            regions = list(self.session_info["region"])
            return regions + ["unknown"] * (self.n_channels - len(regions))
        return ["unknown"] * self.n_channels

    def probes(self) -> list:
        """(probe name, lab region label, spike groups) of each run of consecutive spike groups in the same region."""
        regions = self.channel_regions()
        group_regions = [
            Counter(regions[channel] for channel in channels).most_common(1)[0][0]
            for channels in self.xml_info["shank_channels"]
        ]
        probes = []
        groups = iter(range(1, len(group_regions) + 1))
        for region, run in groupby(group_regions):
            members = [next(groups) for _ in run]
            probes.append((region, members))
        names = [f"{region}_probe" if region != "unknown" else "probe" for region, _ in probes]
        if len(set(names)) != len(names):
            names = [f"probe{index + 1}_{region}" for index, (region, _) in enumerate(probes)]
        return [(name, region, members) for name, (region, members) in zip(names, probes)]

    def add_electrodes(self, nwbfile: NWBFile):
        regions = self.channel_regions()
        shank_channels = self.xml_info["shank_channels"]
        session_info = self.session_info or {}
        ripple_channels = {}
        for table in read_event_files(self.session_path, self.session_id):
            for channel in table["ripple_channel"]:
                ripple_channels.setdefault(channel, []).append(table["name"])

        group_of_spike_group = {}
        for probe_name, region, members in self.probes():
            sizes = Counter(len(shank_channels[group - 1]) for group in members)
            layout = ", ".join(f"{count} group{'s' * (count > 1)} of {size} sites" for size, count in sizes.items())
            where = REGION_NAMES.get(region, region)
            device = nwbfile.create_device(
                name=probe_name,
                description=(
                    f"Silicon probe in the {where} (the lab's region label '{region}'), with {layout} (spike groups "
                    f"{members[0]}-{members[-1]} of the session's .xml file). The papers used NeuroNexus 5x12, 6x10, 8x8 "
                    "and 4x8 and Cambridge NeuroTech 1x64 probes, mounted on microdrives; the model of each probe is "
                    "not stored in the source. " + RECORDING_SYSTEM
                ),
            )
            for group in members:
                n_sites = len(shank_channels[group - 1])
                if n_sites == 4 and len(sizes) > 1:
                    what = (
                        "a group of 4 sites outside the probe's shank groups (on the 64-site probes, likely the probe's "
                        "extra sites; their position is not stored in the source, and the lab labels them with the "
                        "probe's region)"
                    )
                else:
                    what = f"a shank of {n_sites} sites"
                group_regions = sorted({regions[channel] for channel in shank_channels[group - 1]})
                group_location = (
                    REGION_NAMES.get(group_regions[0], group_regions[0]) if len(group_regions) == 1 else "unknown"
                )
                group_of_spike_group[group] = nwbfile.create_electrode_group(
                    name=f"group{group}",
                    description=f"spike group {group} of the lab's files: {what} of the {probe_name}",
                    location=group_location,
                    device=device,
                )

        position = {
            channel: (group, site)
            for group, channels in enumerate(shank_channels, 1)
            for site, channel in enumerate(channels)
        }
        if self.ungrouped_channels:
            group_of_spike_group[0] = nwbfile.create_electrode_group(
                name="no_spike_group",
                description=(
                    "channels of the recording that are in no spike group of the lab's .xml file (channels "
                    f"{', '.join(map(str, self.ungrouped_channels))}): unused probe channels or inputs other than the "
                    "probe; the source does not say which"
                ),
                location="unknown",
                device=nwbfile.create_device(name="other_inputs", description="channels in no spike group of the .xml"),
            )
            position.update({channel: (0, -1) for channel in self.ungrouped_channels})
        columns = dict(
            channel_id="0-based channel number of the lab's .xml, .lfp and .dat files and of its sessionInfo and event files",
            spike_group="1-based spike group (shank) of the lab's .xml file, .clu/.res files and units; 0 for a channel in no spike group",
            shank_electrode_number=(
                "0-based position of the channel in its spike group's channel list in the .xml file (-1 for a channel in no "
                "spike group). The lab's klusta "
                ".prb files place the sites by this position with the same generic staggered layout for groups of 4, 8, "
                "10 and 12 sites, so they do not give the probes' real geometry and no x/y positions are written"
            ),
            region="the lab's region label of the channel (sessionInfo.region); 'hpc' is the probe aimed at dorsal "
            "CA1, not resolved to a subfield",
            theta_channel="the channel is in sessionInfo.thetaChans, the lab's theta reference channels",
            lfp_channel="the channel is in sessionInfo.lfpChans, the lab's representative LFP channels",
            ca1_channel="the channel is sessionInfo.ca1, the lab's CA1 (pyramidal layer) channel",
            ca3_channel="the channel is sessionInfo.ca3, the lab's CA3 channel",
            ls_channel="the channel is sessionInfo.ls, the lab's lateral septum channel",
            ref_channel=(
                "the channel is sessionInfo.refChan, the lab's reference channel; in the event files a channel of this "
                "name is bz_FindRipples' noise channel, which rejects events that also appear on it, not a re-reference"
            ),
            ripple_detection_channel=(
                "names of the lab's event tables (processing/ecephys) whose detections were made on this channel "
                "(their rippleChan); empty if none"
            ),
        )
        for name, description in columns.items():
            nwbfile.add_electrode_column(name=name, description=description)
        for channel in range(self.n_channels):
            group, site = position[channel]
            electrode_group = group_of_spike_group[group]
            nwbfile.add_electrode(
                group=electrode_group,
                group_name=electrode_group.name,
                location=REGION_NAMES.get(regions[channel], regions[channel]),
                channel_id=channel,
                spike_group=group,
                shank_electrode_number=site,
                region=regions[channel],
                theta_channel=channel in session_info.get("theta", []),
                lfp_channel=channel in session_info.get("lfp", []),
                ca1_channel=channel in session_info.get("ca1", []),
                ca3_channel=channel in session_info.get("ca3", []),
                ls_channel=channel in session_info.get("ls", []),
                ref_channel=channel in session_info.get("ref", []),
                ripple_detection_channel=", ".join(ripple_channels.get(channel, [])),
            )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is None:
            return
        # Kept open until the new file has been written
        if str(published_nwb_file_path).startswith(("https://", "http://")):
            import remfile  # stream the earlier file (some are larger than the disk of a cloud job)

            self._published_file = published = h5py.File(remfile.File(str(published_nwb_file_path)), "r")
        else:
            self._published_file = published = h5py.File(published_nwb_file_path, "r")
        published_channels = published["general/extracellular_ephys/electrodes/id"][:]
        all_electrodes = nwbfile.create_electrode_table_region(
            region=list(range(self.n_channels)), description="all channels, in channel order"
        )
        n_samples = STUB_SAMPLES if stub_test else None

        def wrap(series: h5py.Group):
            rows = series["electrodes"][:]
            if series["data"].shape[1] != self.n_channels or sorted(published_channels[rows]) != list(
                range(self.n_channels)
            ):
                raise ValueError(f"{series.name} of the earlier file does not hold each channel once")
            order = np.argsort(published_channels[rows])  # the published column of each channel
            if not np.isclose(series["data"].attrs["conversion"], VOLTS_PER_STEP):
                raise ValueError(f"{series.name} of the earlier file is not in 0.195 uV steps")
            return SliceableDataChunkIterator(data=PublishedColumns(series["data"], order, n_samples))

        source_note = (
            " Taken from the session's file in the earlier version of the dandiset (the lab's int16 values, written "
            "there as float32 with the electrodes in spike-group order), reordered to channel order."
        )
        lfp_group = published["processing/ecephys/LFP"]
        lfp = lfp_group[next(iter(lfp_group))]
        lfp_series = ElectricalSeries(
            name="lfp",
            description=(
                "LFP of all channels: the wide-band signal low-pass filtered and down-sampled to 1250 Hz by the lab "
                "(the .lfp file)." + source_note
            ),
            data=wrap(lfp),
            electrodes=all_electrodes,
            rate=float(lfp["starting_time"].attrs["rate"]),
            conversion=VOLTS_PER_STEP,
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
            LFP(electrical_series=lfp_series)
        )

        wideband_names = [name for name in published["acquisition"] if name.startswith("ElectricalSeries")]
        if self.source_data["include_wideband"] and wideband_names:
            wideband = published["acquisition"][wideband_names[0]]
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description="wide-band signal of all channels at 20 kHz (the lab's .dat file)." + source_note,
                    data=wrap(wideband),
                    electrodes=all_electrodes,
                    rate=float(wideband["starting_time"].attrs["rate"]),
                    conversion=VOLTS_PER_STEP,
                )
            )
