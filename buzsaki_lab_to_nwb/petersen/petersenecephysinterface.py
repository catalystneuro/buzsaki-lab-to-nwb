"""Electrodes, LFP and wide-band signal of a Petersen session (DANDI:000059)."""

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

from .petersenutils import as_dict, as_list, read_mat, read_session_mat, read_session_xml

STUB_SAMPLES = 75_000


class PetersenEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml and session.mat; LFP and wide-band signal from its earlier DANDI file.

    The lab's .lfp and .dat files are not on the public share for most sessions, so the signals are taken from the
    session's "desc-raw" file in DANDI:000059 version 0.250624.0444. Its columns are the .dat channels 0 to n-1 in
    order: the channel with the largest spike waveform of each CellExplorer cell is the column where the cell's mean
    spike is largest. Only its electrodes table was wrong (it put rows 0-9 in shank1, 10-19 in shank2 and so on,
    instead of the channels of each .xml electrode group). The int16 values are copied unchanged.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        published_raw_file_path: Optional[Union[FilePath, str]] = None,  # a path, or a URL to stream
        include_wideband: bool = True,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            published_raw_file_path=published_raw_file_path,
            include_wideband=include_wideband,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.session = read_session_mat(self.session_path, self.session_id)
        self.channels = np.sort(np.concatenate(self.xml_info["groups"]))
        if not np.array_equal(self.channels, np.arange(self.xml_info["n_channels"])):
            raise ValueError(f"The .xml electrode groups of {self.session_id} do not hold channels 0 to n-1 once each")

    def channel_tag(self, name: str) -> set:
        """0-based channels of one of the lab's channelTags (stored 1-based)."""
        tag = as_dict(as_dict(self.session.get("channelTags")).get(name))
        return {int(channel) - 1 for channel in as_list(tag.get("channels"))}

    def channel_regions(self) -> dict:
        """0-based channel to the lab's brain region (session.brainRegions, stored 1-based)."""
        regions = {}
        for region, entry in as_dict(self.session.get("brainRegions")).items():
            for channel in as_list(entry.get("channels")):
                regions[int(channel) - 1] = region
        return regions

    def add_devices(self, nwbfile: NWBFile) -> list:
        """One device per silicon probe of session.extracellular.electrodes; returns (device, first, last channel)."""
        electrodes = as_dict(self.session["extracellular"].get("electrodes"))
        if not electrodes:  # the session.mat files list no probes
            device = nwbfile.create_device(
                name="probe",
                description="silicon probe; the lab's session.mat files of this session list no probe model",
            )
            return [(device, 0, self.xml_info["n_channels"] - 1)]
        names = as_list(electrodes["siliconProbes"])
        companies = as_list(electrodes.get("company")) or [""] * len(names)  # not in the older session.mat
        n_channels = [
            int(n) for n in as_list(electrodes.get("nChannels", electrodes.get("channels")))
        ]  # older: channels
        unique_names = str(electrodes.get("uniqueName", "")).split(", MS")
        if sum(n_channels) != self.xml_info["n_channels"]:
            # Peter_MS13_171127_133330_concat: probes of 128 channels listed for a 96-channel recording
            device = nwbfile.create_device(
                name="probe",
                description=(
                    f"silicon probe(s); the lab's session.mat lists {', '.join(map(str, names))} with "
                    f"{sum(n_channels)} channels in all, which does not match the recording's "
                    f"{self.xml_info['n_channels']} channels, so the probes are not split by channel"
                ),
            )
            return [(device, 0, self.xml_info["n_channels"] - 1)]
        devices = []
        first = 0
        for index, (name, company, count) in enumerate(zip(names, companies, n_channels)):
            location = unique_names[index] if index < len(unique_names) else ""
            location = location.split("| Region:")[-1].strip() if "| Region:" in location else ""
            device = nwbfile.create_device(
                name=f"probe{index + 1}" if len(names) > 1 else "probe",
                description=(
                    f"silicon probe {name}, as listed in the lab's session.mat, channels {first} to {first + count - 1}"
                    + (
                        f"; region and coordinates (AP, ML, DV in mm) in the lab's metadata: {location}"
                        if location
                        else ""
                    )
                ),
                manufacturer=company or None,
            )
            devices.append((device, first, first + count - 1))
            first += count
        if first != self.xml_info["n_channels"]:
            raise ValueError(f"The probes of {self.session_id} hold {first} of {self.xml_info['n_channels']} channels")
        return devices

    def add_electrodes(self, nwbfile: NWBFile):
        devices = self.add_devices(nwbfile)
        regions = self.channel_regions()
        theta, ripple, bad = self.channel_tag("Theta"), self.channel_tag("Ripple"), self.channel_tag("Bad")
        channel_to_group = {}
        for group_index, channels in enumerate(self.xml_info["groups"]):
            device = [device for device, first, last in devices if first <= min(channels) and max(channels) <= last]
            if len(device) != 1:
                raise ValueError(f"Electrode group {group_index + 1} of {self.session_id} spans more than one probe")
            group_regions = {regions.get(channel, "unknown") for channel in channels}
            group = nwbfile.create_electrode_group(
                name=f"shank{group_index + 1}",
                description=(
                    f"electrode group {group_index + 1} of the lab's .xml file ({len(channels)} sites) on {device[0].name}"
                ),
                location=group_regions.pop() if len(group_regions) == 1 else "unknown",
                device=device[0],
            )
            for site, channel in enumerate(channels):
                channel_to_group[channel] = (group, site)

        nwbfile.add_electrode_column(name="channel_id", description="0-based channel number in the lab's .dat and .xml")
        nwbfile.add_electrode_column(
            name="shank_electrode_number", description="0-based position of the channel in its .xml electrode group"
        )
        nwbfile.add_electrode_column(
            name="theta_reference", description="the channel the lab used for theta (session.mat channelTags.Theta)"
        )
        nwbfile.add_electrode_column(
            name="ripple_reference", description="the channel the lab used for ripples (session.mat channelTags.Ripple)"
        )
        nwbfile.add_electrode_column(
            name="bad_channel", description="the lab marked the channel as bad (session.mat channelTags.Bad)"
        )
        for channel in self.channels:
            group, site = channel_to_group[channel]
            nwbfile.add_electrode(
                group=group,
                group_name=group.name,
                location=regions.get(channel, "unknown"),
                channel_id=int(channel),
                shank_electrode_number=site,
                theta_reference=bool(channel in theta),
                ripple_reference=bool(channel in ripple),
                bad_channel=bool(channel in bad),
            )

    def published_columns(self, published: h5py.File) -> np.ndarray:
        """The channel of each column of the earlier file's signals: the .dat channels 0 to n-1, or (in some sessions)
        only the channels in spike groups, in the earlier file's order."""
        ids = published["general/extracellular_ephys/electrodes"]["id"][:]
        self.missing_channels = sorted(set(self.channels.tolist()) - set(ids.tolist()))
        if np.array_equal(ids, self.channels):
            return self.channels
        if len(set(ids.tolist())) != len(ids) or not set(ids.tolist()) <= set(self.channels.tolist()):
            raise ValueError(f"The electrodes of the earlier file of {self.session_id} are not channels of the recording")
        return ids

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        published_raw_file_path = self.source_data["published_raw_file_path"]
        if published_raw_file_path is None:
            return
        # Kept open until the new file has been written
        if str(published_raw_file_path).startswith(("https://", "http://")):
            import remfile  # stream the earlier file (some are larger than the disk of a cloud job)

            self._published_file = published = h5py.File(remfile.File(str(published_raw_file_path)), "r")
        else:
            self._published_file = published = h5py.File(published_raw_file_path, "r")
        order = self.published_columns(published)
        electrodes = nwbfile.create_electrode_table_region(
            region=[int(channel) for channel in order],  # rows are in channel order
            description="the probe channels of the data, in its column order",
        )
        missing_note = (
            f" The earlier file holds no data for channels {', '.join(map(str, self.missing_channels))}, which are in "
            "no spike group of the .xml, so they are not in this series."
            if self.missing_channels
            else ""
        )
        lsb = self.session["extracellular"].get("leastSignificantBit")
        if lsb is None:  # not in the session.mat files: the scaling of the earlier file's LFP
            volts_per_step = float(published["processing/ecephys/LFP/LFP/data"].attrs["conversion"])
        else:
            volts_per_step = float(lsb) * 1e-6

        def series(path: str, name: str, description: str) -> ElectricalSeries:
            source = published[path]
            data = source["data"]
            if data.dtype != np.int16 or data.shape[1] != len(order):
                raise ValueError(
                    f"Unexpected {path} in the earlier file of {self.session_id}: {data.dtype} {data.shape}"
                )
            if not np.isclose(source["data"].attrs["conversion"], volts_per_step):
                raise ValueError(f"The earlier {path} of {self.session_id} has another scaling than session.mat")
            return ElectricalSeries(
                name=name,
                description=description + missing_note,
                data=SliceableDataChunkIterator(data=data[:STUB_SAMPLES] if stub_test else data),
                electrodes=electrodes,
                starting_time=float(source["starting_time"][()]),
                rate=float(source["starting_time"].attrs["rate"]),
                conversion=volts_per_step,
            )

        lfp_series = series(
            "processing/ecephys/LFP/LFP",
            "lfp",
            "LFP of the probe channels: the wide-band signal down-sampled to 1250 Hz by the lab (.lfp file)",
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
            LFP(electrical_series=lfp_series)
        )
        if self.source_data["include_wideband"] and "acquisition/ElectricalSeries" in published:
            nwbfile.add_acquisition(
                series(
                    "acquisition/ElectricalSeries",
                    "ElectricalSeries",
                    "wide-band signal of the probe channels, recorded at 20 kHz on an Intan RHD2000 system (.dat file)",
                )
            )
