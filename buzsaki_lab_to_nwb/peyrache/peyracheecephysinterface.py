"""Electrodes and LFP of a Peyrache session (DANDI:000056)."""

from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .peyracheutils import (
    REGION_DESCRIPTIONS,
    REGION_LOCATIONS,
    load_mat,
    read_session_info,
    read_session_xml,
    read_shank_structure,
    split_session_id,
)

STUB_SAMPLES = 12_500

# Probes of the mice recorded in both the thalamus and the post-subiculum, from the sessions' .xml descriptions
# (anatomical group numbers). In the other mice the devices follow the regions of GeneralInfo.mat.
DUAL_SITE_PROBES = {
    "Mouse24": {"postsubicular_probe": range(1, 5), "thalamic_probe": range(5, 9)},
    "Mouse25": {"postsubicular_probe": range(1, 5), "thalamic_probe": range(5, 9)},
    "Mouse28": {"postsubicular_probe": range(1, 8), "thalamic_probe": range(8, 12)},
}
REGION_DEVICES = {
    "thalamus": "thalamic_probe",
    "postsub": "postsubicular_probe",
    "pfc": "prefrontal_tetrodes",
    "hippocampus": "hippocampal_wires",
}
DEVICE_DESCRIPTIONS = {
    "thalamic_probe": (
        "NeuroNexus silicon probe in the anterior thalamus (Buz64: 8 shanks of 8 sites, or Buz32: 4 shanks of 8 "
        "sites; 200 um between shanks, staggered sites 20 um apart vertically), on a movable drive"
    ),
    "postsubicular_probe": (
        "NeuroNexus silicon probe in the post-subiculum (Buz32: 4 shanks of 8 sites, or Buz64sp: 6 shanks of 10 "
        "sites plus 4 sites above a shank), on a movable drive"
    ),
    "prefrontal_tetrodes": "tetrodes in the medial prefrontal cortex",
    "hippocampal_wires": (
        "50 um tungsten wires aimed at the CA1 pyramidal layer (at least one in the pyramidal layer, as shown by "
        "sharp-wave ripples), for the hippocampal LFP"
    ),
    "other_channels": "channel groups the session's .xml description does not describe",
}
DEVICE_MANUFACTURERS = {"thalamic_probe": "NeuroNexus", "postsubicular_probe": "NeuroNexus"}


class PeyracheEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml file and the lab's GeneralInfo.mat; LFP from the earlier DANDI file.

    The lab's .eeg files are not on the Buzsaki lab share (only the CRCNS th-1 archives hold them), so the LFP is taken
    from the session's file in DANDI:000056 version 0.250624.0430, whose columns are the recording channels 0 to n-1
    in order.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        session_info_file_path: Optional[FilePath] = None,
        published_nwb_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            session_info_file_path=session_info_file_path,
            published_nwb_file_path=published_nwb_file_path,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        general_info_file_path = self.session_path / "Analysis" / "GeneralInfo.mat"
        self.regions = {}
        if general_info_file_path.is_file():
            self.regions = read_shank_structure(load_mat(general_info_file_path, variable_names=["shankStructure"]))

    def depths(self) -> dict:
        """Approximate depth (mm) of the thalamic and post-subicular probes in the CRCNS session table."""
        file_path = self.source_data["session_info_file_path"]
        if file_path is None:
            return {}
        table = read_session_info(Path(file_path))
        if self.session_id not in table.index:
            return {}
        row = table.loc[self.session_id]
        depths = {}
        for device, column in (("thalamic_probe", "thalamus_depth"), ("postsubicular_probe", "postsubiculum_depth")):
            if np.isfinite(float(row[column])):
                depths[device] = float(row[column])
        return depths

    def device_of(self, group: int) -> str:
        mouse, _ = split_session_id(self.session_id)
        for device, groups in DUAL_SITE_PROBES.get(mouse, {}).items():
            if group in groups:
                return device
        return REGION_DEVICES.get(self.regions.get(group), "other_channels")

    def add_electrodes(self, nwbfile: NWBFile):
        depths = self.depths()
        devices = {}
        for group_index, channels in enumerate(self.xml_info["anatomical_groups"]):
            group = group_index + 1
            device_name = self.device_of(group)
            if device_name not in devices:
                description = DEVICE_DESCRIPTIONS[device_name]
                if device_name in depths:
                    description += (
                        f"; approximate depth from the brain surface in this session {depths[device_name]} mm (CRCNS "
                        "th-1 session table)"
                    )
                devices[device_name] = nwbfile.create_device(
                    name=device_name, description=description, manufacturer=DEVICE_MANUFACTURERS.get(device_name)
                )
            region = self.regions.get(group)
            if region in REGION_DESCRIPTIONS:
                region_description = REGION_DESCRIPTIONS[region]
            elif self.regions:
                region_description = (
                    "the lab assigned this group no region (it is not in GeneralInfo.mat shankStructure)"
                )
            else:
                region_description = (
                    "the session has no GeneralInfo.mat, so the lab's region of this group is not known"
                )
            spike_groups = [
                index + 1
                for index, anatomical in enumerate(self.xml_info["spike_to_anatomical"])
                if anatomical == group
            ]
            spike_note = (
                f"; its spikes are in the .clu/.res files of shank {spike_groups[0]}"
                if spike_groups
                else "; no spikes were sorted on it"
            )
            nwbfile.create_electrode_group(
                name=f"group{group}",
                description=f"anatomical channel group {group} of the session's .xml file: {region_description}"
                + spike_note,
                location=REGION_LOCATIONS.get(region, "unknown"),
                device=devices[device_name],
            )

        nwbfile.add_electrode_column(
            name="channel_id", description="channel number in the lab's .xml, .dat and .eeg files"
        )
        nwbfile.add_electrode_column(
            name="shank_electrode_number",
            description="0-indexed position of the channel in its anatomical group's channel list in the .xml file",
        )
        session_info_file_path = self.session_path / f"{self.session_id}.sessionInfo.mat"
        bad_channels = None
        if session_info_file_path.is_file():
            session_info = load_mat(session_info_file_path, variable_names=["sessionInfo"])["sessionInfo"]
            if hasattr(session_info, "badchannels"):
                bad_channels = set(np.atleast_1d(session_info.badchannels).astype(int).tolist())
                nwbfile.add_electrode_column(
                    name="bad_channel",
                    description="the channel is in badchannels of the lab's 2019 buzcode sessionInfo.mat",
                )
        channel_to_group = {
            channel: (group_index + 1, site)
            for group_index, channels in enumerate(self.xml_info["anatomical_groups"])
            for site, channel in enumerate(channels)
        }
        for channel in range(self.xml_info["n_channels"]):
            if channel not in channel_to_group:
                raise ValueError(f"channel {channel} of {self.session_id} is in no anatomical group")
            group_number, site = channel_to_group[channel]
            group = nwbfile.electrode_groups[f"group{group_number}"]
            nwbfile.add_electrode(
                group=group,
                group_name=group.name,
                location=group.location,
                channel_id=channel,
                shank_electrode_number=site,
                **({} if bad_channels is None else dict(bad_channel=channel in bad_channels)),
            )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is None:
            return
        # Kept open until the new file has been written
        self._published_file = published = h5py.File(published_nwb_file_path, "r")
        lfp_group = published["processing/ecephys/LFP"]
        lfp = lfp_group[next(iter(lfp_group.keys()))]
        data = lfp["data"]
        channels = self.published_lfp_channels(published, lfp)
        self.check_lfp_channels(data, channels)
        conversion = float(data.attrs.get("conversion", 1.0))
        rate = float(lfp["starting_time"].attrs["rate"])
        if rate != self.xml_info["lfp_sampling_rate"]:
            raise ValueError(f"the published LFP rate {rate} is not the .xml rate {self.xml_info['lfp_sampling_rate']}")
        n_channels = self.xml_info["n_channels"]
        if len(channels) == n_channels:
            coverage = "all channels"
        else:
            coverage = (
                f"the {len(channels)} channels of the spike groups (of {n_channels}; the earlier conversion left out "
                "the channels of the other groups)"
            )
        xml_step = self.xml_info["voltage_range"] / 2 ** self.xml_info["n_bits"] / self.xml_info["amplification"]
        lfp_series = ElectricalSeries(
            name="lfp",
            description=(
                f"LFP of {coverage} (the lab's .eeg file: the wide-band signal down-sampled to 1250 Hz), as written in "
                "DANDI:000056 version 0.250624.0430, whose columns are these channels in increasing order (checked "
                "against the channels of the lab's buzcode SleepScoreLFP.LFP.mat, where present). The scaling is the "
                f"earlier conversion's {conversion * 1e6:.4g} uV per step (an Amplipex value). The .xml gives a "
                f"{self.xml_info['voltage_range']:g} V range and x{self.xml_info['amplification']:g} amplification "
                f"({xml_step * 1e6:.4g} uV per step), which may be template defaults; the lab has not documented the "
                "gain"
            ),
            data=SliceableDataChunkIterator(data=data[:STUB_SAMPLES] if stub_test else data),
            electrodes=nwbfile.create_electrode_table_region(
                region=[int(channel) for channel in channels], description="channels of the LFP columns"
            ),
            rate=rate,
            starting_time=float(lfp["starting_time"][()]),
            conversion=conversion,
        )
        get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
            LFP(electrical_series=lfp_series)
        )

    def published_lfp_channels(self, published: h5py.File, lfp: h5py.Group) -> np.ndarray:
        """Channel of each published LFP column: the `id` of its row in the published electrodes table.

        The earlier files number their electrodes table rows by channel (with gaps where a channel was left out), and
        their LFP columns are the channels of the spike groups in increasing order.
        """
        rows = lfp["electrodes"][:]
        ids = published["general/extracellular_ephys/electrodes/id"][:]
        channels = ids[rows]
        spike_channels = sorted({channel for group in self.xml_info["spike_groups"] for channel in group})
        if list(channels) == list(range(self.xml_info["n_channels"])):
            return channels
        if list(channels) != spike_channels:
            raise ValueError(f"the published LFP of {self.session_id} holds channels {list(channels)}")
        return channels

    def check_lfp_channels(self, data: h5py.Dataset, channels: np.ndarray):
        """Check the columns against the buzcode SleepScoreLFP channels (1250 Hz down-sampled by 5 to 250 Hz)."""
        file_path = self.session_path / f"{self.session_id}.SleepScoreLFP.LFP.mat"
        if not file_path.is_file():
            return
        lfp = load_mat(file_path)["SleepScoreLFP"]
        n_samples = 50_000
        block = data[: n_samples * 5 : 5]
        for name in ("sw", "th"):
            channel = int(getattr(lfp, f"{name.upper()}chanID"))
            if channel not in channels:
                continue
            column = block[:, list(channels).index(channel)]
            if not np.array_equal(column, np.asarray(getattr(lfp, f"{name}LFP")[:n_samples], dtype=column.dtype)):
                raise ValueError(f"published LFP column of channel {channel} is not the buzcode LFP of that channel")
