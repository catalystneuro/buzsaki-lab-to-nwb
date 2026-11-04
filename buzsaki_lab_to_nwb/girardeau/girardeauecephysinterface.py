"""Electrodes, LFP and wide-band signal of a Girardeau session (DANDI:000061)."""

import re
import warnings
from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile, TimeSeries
from pynwb.ecephys import LFP, ElectricalSeries

from .girardeauutils import (
    UNKNOWN_REGION,
    VOLTS_PER_STEP,
    describe_region_codes,
    load_mat,
    read_evt,
    read_recording_locations,
    read_session_xml,
    region_location,
    shank_channels,
)

STUB_SAMPLES = 100_000
DEVICE_DESCRIPTION = (
    "Three NeuroNexus silicon probes (two with 8 shanks and one with 4 shanks, Buzsaki64 and Buzsaki32 layouts, 160 "
    "recording channels in all) on movable microdrives, implanted above the amygdala on both sides (AP -2.5 mm, ML "
    "3.6 to 5.5 mm from bregma) and in the dorsal hippocampus (CA1, AP -3.5 mm, ML 2.5 mm), as given in the paper; "
    "recorded at 20 kHz on an Amplipex KJE-1001 system (the lab's session.mat)."
)


# A .dat file is read for the auxiliary inputs only below this size (it is read in full)
MAX_DAT_BYTES = 20e9
AUXILIARY_TAGS = ("Accelerometer", "Airpuff", "Rewards")


class FirstColumns:
    """The first rows and columns of a 2D array, read lazily (a memmap or an HDF5 dataset)."""

    def __init__(self, data, n_rows: int, n_columns: int):
        self.data = data
        self.shape = (n_rows, n_columns)
        self.dtype = np.dtype(data.dtype)
        self.ndim = 2

    def __len__(self):
        return self.shape[0]

    def __getitem__(self, selection):
        rows, columns = selection if isinstance(selection, tuple) else (selection, slice(None))
        rows = range(self.shape[0])[rows]
        columns = range(self.shape[1])[columns]
        block = self.data[rows.start : rows.stop, : self.shape[1]] if rows.step == 1 else None
        if block is None:
            raise IndexError("FirstColumns supports contiguous row slices only")
        return np.asarray(block)[:, columns.start : columns.stop : columns.step]


def open_published(path_or_url: str) -> h5py.File:
    """A published NWB file: a local path, or a URL streamed with remfile."""
    if str(path_or_url).startswith(("http://", "https://")):
        import remfile

        return h5py.File(remfile.File(str(path_or_url)), "r")
    return h5py.File(path_or_url, "r")


class GirardeauEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml file and the lab's RecordingLocations.mat; LFP and wide-band signal.

    The LFP comes from the session's .lfp (or .eeg) file when it is in the session folder, otherwise from the
    session's file in DANDI:000061 version 0.250624.0426, whose columns are the recording channels 0 to n-1 in order
    (checked against the .dat and the published wide-band signal of Rat08-20130710). The wide-band signal comes from
    the .dat file, or from the published file; it is written only when asked for.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        subject_folder_path: DirectoryPath,
        published_nwb_file_path: Optional[str] = None,
        include_wideband: bool = True,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            subject_folder_path=subject_folder_path,
            published_nwb_file_path=published_nwb_file_path,
            include_wideband=include_wideband,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.shanks = shank_channels(self.xml_info)
        self.channels = np.sort(np.concatenate(self.shanks))
        if not np.array_equal(self.channels, np.arange(len(self.channels))):
            raise ValueError(f"The probe channels of {self.session_id} are not 0 to n-1")
        self.regions = read_recording_locations(Path(subject_folder_path), self.session_id)

    def shank_region(self, shank: int) -> str:
        codes = self.regions.get(shank)
        return "/".join(codes) if codes else UNKNOWN_REGION

    def add_electrodes(self, nwbfile: NWBFile):
        description = DEVICE_DESCRIPTION
        if self.xml_info["description"]:
            description += " The session's .xml file says: " + " ".join(self.xml_info["description"].split())
        device = nwbfile.create_device(name="silicon_probes", description=description, manufacturer="NeuroNexus")
        codes = {code for shank in range(1, len(self.shanks) + 1) for code in self.shank_region(shank).split("/")}
        for shank, _ in enumerate(self.shanks, start=1):
            region = self.shank_region(shank)
            nwbfile.create_electrode_group(
                name=f"shank{shank}",
                description=(
                    f"shank {shank} (anatomical group {shank} of the .xml file); region code '{region}' from the "
                    "lab's RecordingLocations.mat"
                ),
                location=region_location(region),
                device=device,
            )
        spike_channels = {channel for group in self.xml_info["spike_groups"] for channel in group}
        nwbfile.add_electrode_column(
            name="channel_id", description="channel number in the lab's .xml, .dat and .lfp files"
        )
        nwbfile.add_electrode_column(name="shank", description="shank number (the N of the .clu.N/.res.N files)")
        nwbfile.add_electrode_column(
            name="shank_electrode_number",
            description="0-indexed position of the channel in its shank's channel list in the .xml file",
        )
        nwbfile.add_electrode_column(
            name="region",
            description=(
                "the lab's region code of the shank in RecordingLocations.mat (shankInfo), unchanged; 'unknown' for "
                "shanks the file does not place. The codes look like Paxinos and Watson abbreviations (not confirmed "
                "by the lab): " + describe_region_codes(codes)
            ),
        )
        nwbfile.add_electrode_column(
            name="in_spike_detection",
            description="the channel is in its shank's spike group of the .xml file (used for spike sorting)",
        )
        channel_to_shank = {
            channel: (shank, site)
            for shank, channels in enumerate(self.shanks, start=1)
            for site, channel in enumerate(channels)
        }
        for channel in self.channels:
            shank, site = channel_to_shank[channel]
            group = nwbfile.electrode_groups[f"shank{shank}"]
            nwbfile.add_electrode(
                group=group,
                group_name=group.name,
                location=group.location,
                channel_id=int(channel),
                shank=shank,
                shank_electrode_number=site,
                region=self.shank_region(shank),
                in_spike_detection=bool(channel in spike_channels),
            )

    def local_signal(self, suffixes) -> Optional[np.memmap]:
        for suffix in suffixes:
            file_path = self.session_path / f"{self.session_id}{suffix}"
            if file_path.is_file():
                data = np.memmap(file_path, dtype=np.int16, mode="r")
                return data.reshape(-1, self.xml_info["n_channels"])
        return None

    def published(self) -> Optional[h5py.File]:
        if self.source_data["published_nwb_file_path"] is None:
            return None
        if not hasattr(self, "_published_file"):
            # Kept open until the new file has been written
            self._published_file = open_published(self.source_data["published_nwb_file_path"])
        return self._published_file

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        n_electrodes = len(self.channels)
        electrodes = nwbfile.create_electrode_table_region(
            region=list(range(n_electrodes)), description="all probe electrodes"
        )

        def select(data, source: str):
            if data.shape[1] < n_electrodes:
                raise ValueError(f"{source} has {data.shape[1]} columns for {n_electrodes} probe channels")
            rows = min(STUB_SAMPLES, data.shape[0]) if stub_test else data.shape[0]
            return SliceableDataChunkIterator(data=FirstColumns(data, rows, n_electrodes), display_progress=True)

        lfp = self.local_signal([".lfp", ".eeg"])
        lfp_source = "the lab's .lfp file (the wide-band signal down-sampled by the lab)"
        if lfp is None and self.published() is not None:
            lfp = self.published()["processing/ecephys/LFP/LFP/data"]
            lfp_source = (
                "the session's file in DANDI:000061 version 0.250624.0426 (the share has no .lfp file for this session), "
                "whose columns are the recording channels in order"
            )
        if lfp is not None:
            lfp_series = ElectricalSeries(
                name="lfp",
                description=(
                    f"LFP of the probe channels at {self.xml_info['lfp_sampling_rate']:g} Hz, from {lfp_source}; in "
                    "steps of 0.3815 uV (the least significant bit in the lab's session.mat; the .xml settings would "
                    "give 0.305 uV)"
                ),
                data=select(lfp, "the LFP"),
                electrodes=electrodes,
                rate=self.xml_info["lfp_sampling_rate"],
                conversion=VOLTS_PER_STEP,
            )
            ecephys = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")
            ecephys.add(LFP(electrical_series=lfp_series))

        self.add_auxiliary_inputs(nwbfile, stub_test=stub_test)

        if not self.source_data["include_wideband"]:
            return
        wideband = self.local_signal([".dat"])
        wideband_source = "the lab's .dat file"
        if wideband is None and self.published() is not None and "acquisition/ElectricalSeries" in self.published():
            wideband = self.published()["acquisition/ElectricalSeries/data"]
            wideband_source = "the session's file in DANDI:000061 version 0.250624.0426"
        if wideband is not None:
            nwbfile.add_acquisition(
                ElectricalSeries(
                    name="ElectricalSeries",
                    description=(
                        f"wide-band signal of the probe channels at {self.xml_info['sampling_rate']:g} Hz, from "
                        f"{wideband_source}; in steps of 0.3815 uV (see the LFP)"
                    ),
                    data=select(wideband, "the wide-band signal"),
                    electrodes=electrodes,
                    rate=self.xml_info["sampling_rate"],
                    conversion=VOLTS_PER_STEP,
                )
            )

    def channel_tags(self) -> tuple:
        """The auxiliary channels as 0-indexed channels, {tag: [channels]}, and where they come from.

        Rat08 and Rat09: the session.mat channelTags (1-indexed). Rat10 and Rat11 have no such tags; their .xml
        description lists them 0-indexed ("Behavior : accelerometer : 166 167 168", "Airpuff : 169", "Water rewards :
        170 171", next to "Amygdala Right - voies 0-63"). Channels beyond the file's channel count are refused.
        """
        tags, origin = {}, ""
        session_mat_path = self.session_path / f"{self.session_id}.session.mat"
        if session_mat_path.is_file():
            channel_tags = load_mat(session_mat_path)["session"].channelTags
            tags = {
                tag: [int(channel) - 1 for channel in np.atleast_1d(getattr(channel_tags, tag).channels)]
                for tag in AUXILIARY_TAGS
                if tag in channel_tags._fieldnames
            }
            origin = "the session.mat channelTags, 1-indexed there"
        if not tags:
            text = self.xml_info["description"]
            for tag, pattern in (
                ("Accelerometer", r"accelerometer\s*:\s*([\d ]+)"),
                ("Airpuff", r"Airpuff\s*:\s*([\d ]+)"),
                ("Rewards", r"Water rewards\s*:\s*([\d ]+)"),
            ):
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    tags[tag] = [int(channel) for channel in match.group(1).split()]
            origin = "the .xml description, 0-indexed there"
        out_of_range = [c for channels in tags.values() for c in channels if c >= self.xml_info["n_channels"]]
        if out_of_range:
            warnings.warn(
                f"{self.session_id}: auxiliary channels {out_of_range} from {origin} are beyond the "
                f"{self.xml_info['n_channels']} channels of the recording; auxiliary inputs not converted"
            )
            return {}, origin
        return tags, origin

    def auxiliary_source(self) -> tuple:
        """(samples, rate, description) of a source holding all channels, or (None, None, reason)."""
        lfp = self.local_signal([".lfp", ".eeg"])
        if lfp is not None:
            return lfp, self.xml_info["lfp_sampling_rate"], "the lab's .lfp file (all channels down-sampled by the lab)"
        published = self.published()
        n_channels = self.xml_info["n_channels"]
        if published is not None:
            for location, rate in (
                ("processing/ecephys/LFP/LFP/data", self.xml_info["lfp_sampling_rate"]),
                ("acquisition/ElectricalSeries/data", self.xml_info["sampling_rate"]),
            ):
                if location in published and published[location].shape[1] == n_channels:
                    return published[location], rate, "the session's file in DANDI:000061 version 0.250624.0426"
        dat_path = self.session_path / f"{self.session_id}.dat"
        if dat_path.is_file() and dat_path.stat().st_size < MAX_DAT_BYTES:
            return self.local_signal([".dat"]), self.xml_info["sampling_rate"], "the lab's .dat file"
        return None, None, "no .lfp file, no published series with the auxiliary channels, and no .dat under 20 GB"

    def reward_sides(self, samples, rate: float, channels: list) -> dict:
        """Side of each reward line, from its step at the times of the .lrw.evt and .rrw.evt events."""
        steps = {}
        for side, suffix in (("left", ".lrw.evt"), ("right", ".rrw.evt")):
            evt_path = self.session_path / f"{self.session_id}{suffix}"
            if not evt_path.is_file() or evt_path.stat().st_size == 0:
                return {}
            indices = (read_evt(evt_path).ms.to_numpy() / 1000 * rate).astype(int)
            indices = indices[(indices > rate) & (indices < samples.shape[0] - rate)]
            before = np.array(
                [np.asarray(samples[i - int(0.1 * rate) : i - int(0.01 * rate), channels]).mean(0) for i in indices]
            )
            after = np.array([np.asarray(samples[i : i + int(0.05 * rate), channels]).mean(0) for i in indices])
            steps[side] = (after - before).mean(0)
        sides = {}
        for index, channel in enumerate(channels):
            left, right = steps["left"][index], steps["right"][index]
            if left > 10 * max(abs(right), 1):
                sides[channel] = ("left", left, right)
            elif right > 10 * max(abs(left), 1):
                sides[channel] = ("right", left, right)
        return sides

    def add_auxiliary_inputs(self, nwbfile: NWBFile, stub_test: bool = False):
        """Accelerometer, air-puff and reward inputs (see channel_tags), in the system's raw int16 steps."""
        tags, origin = self.channel_tags()
        if not tags:
            return
        samples, rate, source = self.auxiliary_source()
        if samples is None:
            warnings.warn(f"{self.session_id}: auxiliary inputs not converted: {source}")
            return
        rows = min(STUB_SAMPLES, samples.shape[0]) if stub_test else samples.shape[0]
        all_channels = sorted(channel for channels in tags.values() for channel in channels)
        if isinstance(samples, h5py.Dataset):
            block = samples[:rows, all_channels]
        else:
            block = np.asarray(samples[:rows, all_channels])
        columns = {channel: block[:, index] for index, channel in enumerate(all_channels)}
        common = (
            f"{rate:g} Hz, from {source}; in the recording system's raw int16 steps, as the scaling of these inputs "
            "is not documented (the 0.3815 uV of the probe channels does not apply to them). Channel numbers are "
            f"0-indexed here (from {origin})"
        )

        def as_in_source(channels):
            offset = 1 if origin.startswith("the session.mat") else 0
            return ", ".join(str(channel + offset) for channel in channels)

        if "Accelerometer" in tags:
            channels = tags["Accelerometer"]
            nwbfile.add_acquisition(
                TimeSeries(
                    name="accelerometer",
                    description=(
                        f"head-stage accelerometer, channels {channels} ('Accelerometer' in {origin}: "
                        f"{as_in_source(channels)}); columns are axis 1 to 3 in channel order, as the source does not say "
                        f"which axis is which; {common}"
                    ),
                    data=np.column_stack([columns[channel] for channel in channels]),
                    unit="a.u.",
                    rate=float(rate),
                )
            )
        if "Airpuff" in tags:
            (channel,) = tags["Airpuff"]
            nwbfile.add_acquisition(
                TimeSeries(
                    name="air_puff_input",
                    description=(
                        f"air-puff input, channel {channel} ('Airpuff' in {origin}: {as_in_source([channel])}); the "
                        f"events of the .puf.evt file are its rising edges; {common}"
                    ),
                    data=columns[channel],
                    unit="a.u.",
                    rate=float(rate),
                )
            )
        if "Rewards" in tags:
            channels = tags["Rewards"]
            sides = self.reward_sides(samples, rate, channels) if not stub_test else {}
            for channel in channels:
                if channel in sides:
                    side, left, right = sides[channel]
                    name = f"{side}_reward_input"
                    side_text = (
                        f"the {side} reward line: at the .{side[0]}rw.evt events it steps up by {max(left, right):.0f} "
                        f"steps on average, and by {min(left, right):.0f} at the other side's events (the source does "
                        "not say which channel is which side)"
                    )
                else:
                    name = f"reward_input_ch{channel}"
                    side_text = "the side could not be told from the .lrw.evt and .rrw.evt events"
                nwbfile.add_acquisition(
                    TimeSeries(
                        name=name,
                        description=(
                            f"water-reward input, channel {channel} ('Rewards' in {origin}: "
                            f"{as_in_source(channels)}); {side_text}; {common}"
                        ),
                        data=columns[channel],
                        unit="a.u.",
                        rate=float(rate),
                    )
                )
