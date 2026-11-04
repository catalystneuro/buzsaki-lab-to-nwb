"""Electrodes, LFP and wide-band signal of a Girardeau session (DANDI:000061)."""

from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .girardeauutils import (
    UNKNOWN_REGION,
    VOLTS_PER_STEP,
    describe_region_codes,
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
