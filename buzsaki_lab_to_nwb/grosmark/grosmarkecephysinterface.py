"""Electrodes, LFP, neck EMG and accelerometer of a Grosmark session (DANDI:000044)."""

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

from .grosmarkutils import (
    MISC_CHANNELS,
    NO_ACCELEROMETER_ON_MAZE,
    PROBE_DESCRIPTIONS,
    PROBES,
    VOLTS_PER_STEP,
    read_session_xml,
    split_session_id,
)

STUB_SAMPLES = 75_000
HEMISPHERES = ("left", "right")
CA1 = "CA1 field of hippocampus"


class GrosmarkEcephysInterface(BaseDataInterface):
    """Electrodes from the session's .xml file and the lab's channel map (Channel_Orderings.pdf); the LFP, neck EMG and
    accelerometer from the session's .eeg file, or the LFP alone from the session's earlier DANDI file.

    The .eeg file holds every channel of the recording at 1250 Hz: the 128 probe channels, then the EMG and
    accelerometer channels, which are in no spike group of the .xml file.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        eeg_file_path: Optional[FilePath] = None,
        published_nwb_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            eeg_file_path=eeg_file_path,
            published_nwb_file_path=published_nwb_file_path,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.rat, _ = split_session_id(self.session_id)
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.probe = PROBES[self.rat]
        self.channels = np.sort(np.concatenate(self.xml_info["shank_channels"]))
        if not np.array_equal(self.channels, np.arange(len(self.channels))):
            raise ValueError(f"The spike-group channels of {self.session_id} are not 0 to n-1")

    def shank_groups(self) -> list:
        """(electrode group name, hemisphere, is the extra-site group, description) of each spike group, in order.

        Spike groups 1 to n/2 are on the left probe and the rest on the right one. On the Buzsaki64sp probes the last
        spike group of each probe holds its 4 extra sites.
        """
        n_groups = len(self.xml_info["shank_channels"])
        per_probe = n_groups // 2
        groups = []
        for index in range(n_groups):
            hemisphere = HEMISPHERES[index // per_probe]
            shank = index % per_probe + 1
            is_extra = self.probe == "Buzsaki64sp" and shank == per_probe
            if is_extra:
                name = f"{hemisphere}_extra_sites"
                description = (
                    f"the 4 extra sites of the {hemisphere} probe (spike group {index + 1} of the lab's files), spaced "
                    "every 1.25 mm starting 1.25 mm from the tip of shank 4, so above CA1 and not in its pyramidal "
                    "layer; the structures they sit in are not documented"
                )
            else:
                name = f"{hemisphere}_shank{shank}"
                description = (
                    f"shank {shank} of the {hemisphere} probe (spike group {index + 1} of the lab's files), in the "
                    f"CA1 pyramidal layer of the {hemisphere} dorsal hippocampus"
                )
            groups.append((name, hemisphere, is_extra, description))
        return groups

    def add_electrodes(self, nwbfile: NWBFile):
        devices = {
            hemisphere: nwbfile.create_device(
                name=f"{self.probe}_{hemisphere}",
                description=f"{PROBE_DESCRIPTIONS[self.probe]}, in the {hemisphere} hemisphere. Recorded with an "
                "Amplipex KJE-1001 amplifier (+-5 V range, 16 bits, x400 gain) at 20 kHz.",
                manufacturer="NeuroNexus",
            )
            for hemisphere in HEMISPHERES
        }
        nwbfile.add_electrode_column(name="channel_id", description="0-based channel number of the .xml and .eeg files")
        nwbfile.add_electrode_column(
            name="spike_group", description="1-based spike group (shank) number of the lab's files and unit IDs"
        )
        nwbfile.add_electrode_column(
            name="shank_electrode_number",
            description=(
                "0-based position of the channel in its spike group's channel list; the lab ordered the channels to "
                "follow the sites' spatial order on the shank (CRCNS hc-11 description), but whether this runs from "
                "the tip upward or downward toward it is not documented"
            ),
        )
        nwbfile.add_electrode_column(name="hemisphere", description="hemisphere of the probe: left or right")
        nwbfile.add_electrode_column(
            name="bad_electrode",
            description=(
                "the channel is marked skip in the session's .xml file: the lab left it out of further analysis due to "
                "low amplitude or instability (Channel_Orderings.pdf)"
            ),
        )
        for index, (channels, (name, hemisphere, is_extra, description)) in enumerate(
            zip(self.xml_info["shank_channels"], self.shank_groups())
        ):
            group = nwbfile.create_electrode_group(
                name=name,
                description=description,
                location="unknown" if is_extra else CA1,
                device=devices[hemisphere],
            )
            for site, channel in enumerate(channels):
                nwbfile.add_electrode(
                    group=group,
                    group_name=group.name,
                    location=group.location,
                    channel_id=int(channel),
                    spike_group=index + 1,
                    shank_electrode_number=site,
                    hemisphere=hemisphere,
                    bad_electrode=channel in self.xml_info["skipped_channels"],
                )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        # The electrodes table rows are in spike-group order; the LFP columns are channels 0 to n-1
        channel_ids = list(nwbfile.electrodes["channel_id"][:])
        lfp_electrodes = nwbfile.create_electrode_table_region(
            region=[channel_ids.index(channel) for channel in self.channels],
            description="all probe channels, in channel order",
        )
        n_samples = STUB_SAMPLES if stub_test else None
        scaling = (
            f" Scaled to volts with {VOLTS_PER_STEP * 1e6:.4f} uV per step: the Amplipex system's +-5 V range over 16 "
            "bits at x400 gain (the .meta files of the raw recordings); the .xml files' 20 V and x1000 are not used."
        )
        concatenation = (
            " The lab concatenated the PRE, MAZE and POST recordings into one file, so times are seconds into the "
            "concatenated recording."
        )
        eeg_file_path = self.source_data["eeg_file_path"]
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        ecephys_module = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")

        if eeg_file_path is not None:
            n_channels = self.xml_info["n_channels"]
            eeg = np.memmap(eeg_file_path, dtype=np.int16, mode="r")
            if eeg.size % n_channels:
                raise ValueError(f"{eeg_file_path} does not hold whole frames of {n_channels} channels")
            eeg = eeg.reshape(-1, n_channels)[:n_samples]
            rate = self.xml_info["lfp_sampling_rate"]
            lfp_series = ElectricalSeries(
                name="lfp",
                description=(
                    "LFP of all probe channels: the 20 kHz wide-band signal down-sampled to 1250 Hz by the lab "
                    "(.eeg file)." + scaling + concatenation
                ),
                data=SliceableDataChunkIterator(data=eeg[:, : len(self.channels)]),
                electrodes=lfp_electrodes,
                rate=rate,
                conversion=VOLTS_PER_STEP,
            )
            ecephys_module.add(LFP(electrical_series=lfp_series))

            misc = MISC_CHANNELS[self.rat]
            emg = misc["emg"]
            nwbfile.add_acquisition(
                TimeSeries(
                    name="neck_emg",
                    description=(
                        f"neck-muscle EMG, on channel{'s' if len(emg) > 1 else ''} {', '.join(map(str, emg))} "
                        "(0-based) of the .eeg file (Channel_Orderings.pdf), down-sampled to 1250 Hz by the lab, in "
                        "the recording system's int16 steps: the gain of these inputs is not documented."
                        + concatenation
                    ),
                    data=SliceableDataChunkIterator(data=eeg[:, emg[0] : emg[-1] + 1]),
                    unit="a.u.",
                    rate=rate,
                )
            )
            accelerometer = misc["accelerometer"]
            maze_note = (
                " Not valid during the MAZE epoch: the accelerometer's power supply was used for the head-mounted "
                "LEDs of the position tracking (CRCNS hc-11 description)."
                if self.rat in NO_ACCELEROMETER_ON_MAZE
                else ""
            )
            nwbfile.add_acquisition(
                TimeSeries(
                    name="accelerometer",
                    description=(
                        f"head-mounted 3-axis accelerometer, on channels {', '.join(map(str, accelerometer))} "
                        "(0-based) of the .eeg file (Channel_Orderings.pdf), down-sampled to 1250 Hz by the lab, in "
                        "the recording system's int16 steps: the scaling to acceleration and the axes are not "
                        "documented." + maze_note + concatenation
                    ),
                    data=SliceableDataChunkIterator(data=eeg[:, accelerometer[0] : accelerometer[-1] + 1]),
                    unit="a.u.",
                    rate=rate,
                )
            )
        elif published_nwb_file_path is not None:
            # Kept open until the new file has been written
            self._published_file = published = h5py.File(published_nwb_file_path, "r")
            lfp_group = published["processing/ecephys/LFP"]
            lfp = lfp_group["LFP"] if "LFP" in lfp_group else lfp_group["lfp"]
            if lfp["data"].shape[1] != len(self.channels):
                raise ValueError(f"The earlier DANDI file has {lfp['data'].shape[1]} LFP columns")
            lfp_series = ElectricalSeries(
                name="lfp",
                description=(
                    "LFP of all probe channels: the 20 kHz wide-band signal down-sampled to 1250 Hz by the lab, "
                    "taken from the session's earlier DANDI file, which holds the probe channels of the .eeg file "
                    "in channel order." + scaling + concatenation
                ),
                data=SliceableDataChunkIterator(data=lfp["data"][:n_samples] if stub_test else lfp["data"]),
                electrodes=lfp_electrodes,
                rate=float(lfp["starting_time"].attrs["rate"]),
                conversion=VOLTS_PER_STEP,
            )
            ecephys_module.add(LFP(electrical_series=lfp_series))
