"""Electrodes, LFP and wide-band signal of a Huszar session (DANDI:000552)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from .huszarutils import as_list, read_session

# The paper's probes were implanted in dorsal CA1; session.mat gives no brain region
LOCATION = "CA1"
STUB_SAMPLES = 75_000

GAIN_NOTE = (
    "scaled to volts with session.mat extracellular.leastSignificantBit ({lsb} uV per step, the Intan RHD2000 step); "
    "the .xml gives 20 V and x1000 (0.305 uV per step), template values of the lab's files"
)


class HuszarEcephysInterface(BaseDataInterface):
    """Electrodes from session.mat and chanMap.mat; LFP from the .lfp file and wide-band signal from the .dat file.

    The Globus copy of the source has a .lfp file for one session (e13_26m1_211119) and no .dat files.
    """

    def __init__(
        self, folder_path: DirectoryPath, write_lfp: bool = True, write_raw: bool = True, verbose: bool = False
    ):
        super().__init__(folder_path=folder_path, write_lfp=write_lfp, write_raw=write_raw, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.session = read_session(self.session_path)
        self.extracellular = self.session["extracellular"]
        self.n_channels = int(self.extracellular["nChannels"])
        self.volts_per_step = float(self.extracellular["leastSignificantBit"]) * 1e-6
        # 1-indexed channel lists of the lab's electrode groups (shank sides)
        self.group_channels = [
            np.atleast_1d(channels).astype(int)
            for channels in as_list(self.extracellular["electrodeGroups"]["channels"])
        ]

    def add_electrodes(self, nwbfile: NWBFile):
        layout = self.session.get("analysisTags", {}).get("probesLayout", "")
        equipment = self.session.get("timeSeries", {}).get("dat", {}).get("equipment") or "Intan RHD2000"
        device = nwbfile.create_device(
            name="Probe",
            description=(
                f"{self.n_channels}-channel silicon probe in {len(self.group_channels)} electrode groups"
                + (f", {layout} site layout" if isinstance(layout, str) and layout else "")
                + f" (session.mat); recorded with {equipment}"
            ),
        )
        for index, _ in enumerate(self.group_channels):
            nwbfile.create_electrode_group(
                name=f"Group {index + 1}",
                description=f"electrode group {index + 1} of session.mat extracellular.electrodeGroups",
                location=LOCATION,
                device=device,
            )

        channel_map_path = self.session_path / "chanMap.mat"
        channel_map = read_mat(channel_map_path) if channel_map_path.is_file() else None
        if channel_map is not None and not np.array_equal(
            np.asarray(channel_map["chanMap0ind"]).astype(int), np.arange(self.n_channels)
        ):
            channel_map = None  # the coordinates are only taken when the map lists the channels in order
        bad_channels = set()
        tags = self.session.get("channelTags") or {}
        if isinstance(tags.get("Bad"), dict):
            bad_channels = {int(channel) - 1 for channel in np.atleast_1d(tags["Bad"].get("channels", []))}

        channel_to_group = {
            int(channel) - 1: index for index, channels in enumerate(self.group_channels) for channel in channels
        }
        nwbfile.add_electrode_column(
            name="channel_name", description="0-indexed channel number in the lab's .dat and .lfp files"
        )
        nwbfile.add_electrode_column(
            name="bad_channel", description="the lab marked the channel as bad (session.mat channelTags.Bad)"
        )
        if channel_map is not None:
            nwbfile.add_electrode_column(name="shank", description="shank number of the channel (chanMap.mat kcoords)")
            if "side" in channel_map:
                nwbfile.add_electrode_column(
                    name="probe_side", description="side of the shank the site is on (chanMap.mat side)"
                )
        for channel in range(self.n_channels):
            group = nwbfile.electrode_groups[f"Group {channel_to_group[channel] + 1}"]
            values = dict(channel_name=str(channel), bad_channel=channel in bad_channels)
            if channel_map is not None:
                values.update(
                    rel_x=float(channel_map["xcoords"][channel]),
                    rel_y=float(channel_map["ycoords"][channel]),
                    shank=int(channel_map["kcoords"][channel]),
                )
                if "side" in channel_map:
                    values["probe_side"] = str(channel_map["side"][channel])
            nwbfile.add_electrode(group=group, group_name=group.name, location=LOCATION, **values)

    def _series(self, nwbfile, file_path: Path, name: str, rate: float, description: str, stub_test: bool):
        data = np.memmap(file_path, dtype=np.int16, mode="r")
        data = data[: data.size - data.size % self.n_channels].reshape(-1, self.n_channels)
        if stub_test:
            data = data[:STUB_SAMPLES]
        return ElectricalSeries(
            name=name,
            description=description,
            data=SliceableDataChunkIterator(data=data),
            electrodes=nwbfile.create_electrode_table_region(
                region=list(range(self.n_channels)), description="all channels"
            ),
            rate=rate,
            conversion=self.volts_per_step,
        )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.add_electrodes(nwbfile)
        gain_note = GAIN_NOTE.format(lsb=self.extracellular["leastSignificantBit"])

        lfp_path = self.session_path / f"{self.session_id}.lfp"
        if self.source_data["write_lfp"] and lfp_path.is_file() and lfp_path.stat().st_size:
            rate = float(self.extracellular.get("srLfp", 1250))
            series = self._series(
                nwbfile,
                lfp_path,
                "LFP",
                rate,
                f"LFP of all channels, the lab's .lfp file (the wide-band signal down-sampled to {rate:g} Hz, rate from "
                f"session.mat srLfp), {gain_note}",
                stub_test,
            )
            get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(
                LFP(name="LFP", electrical_series=series)
            )

        raw_path = self.session_path / f"{self.session_id}.dat"
        if self.source_data["write_raw"] and raw_path.is_file() and raw_path.stat().st_size:
            rate = float(self.extracellular["sr"])
            nwbfile.add_acquisition(
                self._series(
                    nwbfile,
                    raw_path,
                    "ElectricalSeries",
                    rate,
                    f"wide-band signal of all channels at {rate:g} Hz (session.mat sr), the lab's .dat file, {gain_note}",
                    stub_test,
                )
            )
