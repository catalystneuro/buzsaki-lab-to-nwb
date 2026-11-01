"""Authors: Cody Baker and Ben Dichter."""

from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile
from pynwb.ecephys import LFP, ElectricalSeries, SpikeEventSeries
from pynwb.misc import DecompositionSeries

from .watsonutils import bandpass_phase, get_conversion_to_volts, read_basic_metadata, read_session_xml

REFERENCE_DESCRIPTIONS = dict(
    up_reference=("UPDecompositionSeries", "this electrode was used to calculate UP-states"),
    spindle_reference=("SpindleDecompositionSeries", "this electrode was used to calculate slow-wave sleep"),
    theta_reference=("ThetaDecompositionSeries", "this electrode was used to calculate theta canonical bands"),
)
PHASE_BANDS = dict(theta=(4, 10), gamma=(30, 80))
STUB_LFP_SAMPLES = 75_000  # one minute at 1250 Hz
STUB_SPIKES = 50


class WatsonEcephysInterface(BaseDataInterface):
    """Electrodes, LFP, LFP phase decompositions and spike waveforms of a Watson session.

    The LFP is read from the session's .lfp file when there is one. Otherwise it can be taken from the
    ElectricalSeries `processing/ecephys/LFP/lfp` of a previously published NWB file of the session, which holds
    the int16 samples of the shank channels in ascending channel order.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        lfp_file_path: Optional[FilePath] = None,
        published_nwb_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            lfp_file_path=lfp_file_path,
            published_nwb_file_path=published_nwb_file_path,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.channels = np.sort(np.concatenate(self.xml_info["shank_channels"]))

        basic_metadata_file_path = self.session_path / f"{self.session_id}_BasicMetaData.mat"
        if basic_metadata_file_path.is_file():
            self.basic_metadata = read_basic_metadata(basic_metadata_file_path)
        else:
            self.basic_metadata = dict(cortex_region="unknown")

    def get_lfp_data(self):
        """Return the int16 (samples, channels) LFP of the shank channels, or None when there is no source."""
        lfp_file_path = self.source_data["lfp_file_path"]
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        n_channels = self.xml_info["n_channels"]
        if lfp_file_path is not None:
            n_values = Path(lfp_file_path).stat().st_size // np.dtype(np.int16).itemsize
            if n_values % n_channels:
                raise ValueError(
                    f"{lfp_file_path} holds {n_values} int16 values, which is not a multiple of the "
                    f"{n_channels} channels in the xml file."
                )
            lfp = np.memmap(lfp_file_path, dtype=np.int16, mode="r").reshape(-1, n_channels)
            return lfp[:, self.channels]
        if published_nwb_file_path is not None:
            # Kept open until the new file has been written
            self._published_file = h5py.File(published_nwb_file_path, "r")
            lfp = self._published_file["processing/ecephys/LFP/lfp/data"]
            if lfp.shape[1] != len(self.channels):
                raise ValueError(
                    f"The LFP in {published_nwb_file_path} has {lfp.shape[1]} columns, but the xml file lists "
                    f"{len(self.channels)} shank channels, so its columns cannot be matched to channels."
                )
            return lfp
        return None

    def add_electrodes(self, nwbfile: NWBFile, metadata: dict):
        device = nwbfile.create_device(**metadata["Devices"]["implant"])
        location = self.basic_metadata["cortex_region"]
        channel_to_shank = {
            channel: (shank_index, electrode_number)
            for shank_index, channels in enumerate(self.xml_info["shank_channels"])
            for electrode_number, channel in enumerate(channels)
        }
        for shank_index, _ in enumerate(self.xml_info["shank_channels"]):
            name = f"shank{shank_index + 1}"
            nwbfile.create_electrode_group(
                name=name, description=f"{name} electrodes", location=location, device=device
            )

        nwbfile.add_electrode_column(name="channel_id", description="channel number in the .xml, .dat and .lfp files")
        nwbfile.add_electrode_column(name="shank_electrode_number", description="0-indexed channel within a shank")
        references = {
            name: self.basic_metadata[name]
            for name in REFERENCE_DESCRIPTIONS
            if self.basic_metadata.get(name) in self.channels
        }
        for name in references:
            nwbfile.add_electrode_column(name=name, description=REFERENCE_DESCRIPTIONS[name][1])

        for channel in self.channels:
            shank_index, electrode_number = channel_to_shank[channel]
            group = nwbfile.electrode_groups[f"shank{shank_index + 1}"]
            nwbfile.add_electrode(
                group=group,
                group_name=group.name,
                location=location,
                channel_id=int(channel),
                shank_electrode_number=electrode_number,
                **{name: bool(channel == reference) for name, reference in references.items()},
            )
        return references

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        references = self.add_electrodes(nwbfile=nwbfile, metadata=metadata)
        ecephys_module = get_module(
            nwbfile=nwbfile, name="ecephys", description="processed extracellular electrophysiology data"
        )
        conversion = get_conversion_to_volts(self.xml_info)
        lfp_sampling_rate = self.xml_info["lfp_sampling_rate"]

        lfp_data = self.get_lfp_data()
        if lfp_data is not None:
            if stub_test:
                lfp_data = lfp_data[:STUB_LFP_SAMPLES]
            lfp_series = ElectricalSeries(
                name="lfp",
                description="LFP of all shank electrodes, downsampled from the wideband signal by the lab",
                data=SliceableDataChunkIterator(data=lfp_data),
                electrodes=nwbfile.create_electrode_table_region(
                    region=list(range(len(self.channels))), description="all shank electrodes"
                ),
                rate=lfp_sampling_rate,
                conversion=conversion,
            )
            ecephys_module.add(LFP(electrical_series=lfp_series))

            for reference_name, reference_channel in references.items():
                series_name, _ = REFERENCE_DESCRIPTIONS[reference_name]
                column = int(np.flatnonzero(self.channels == reference_channel)[0])
                signal = np.asarray(lfp_data[:, column], dtype=float)
                phases = np.stack([bandpass_phase(signal, lfp_sampling_rate, band) for band in PHASE_BANDS.values()])
                decomposition_series = DecompositionSeries(
                    name=series_name,
                    description=(
                        f"Theta and gamma phase of the LFP of the {reference_name.replace('_', '-')} channel "
                        f"(channel {reference_channel}): 4th-order zero-phase Butterworth band-pass, then the "
                        "angle of the Hilbert transform"
                    ),
                    data=phases.T[:, np.newaxis, :],
                    rate=lfp_sampling_rate,
                    source_timeseries=lfp_series,
                    metric="phase",
                    unit="radians",
                )
                for band_name, band_limits in PHASE_BANDS.items():
                    decomposition_series.add_band(band_name=band_name, band_limits=band_limits)
                ecephys_module.add(decomposition_series)

        for shank_index, shank_channels in enumerate(self.xml_info["shank_channels"]):
            self.add_spike_waveforms(
                nwbfile=nwbfile,
                ecephys_module=ecephys_module,
                shank_number=shank_index + 1,
                shank_channels=shank_channels,
                conversion=conversion,
                stub_test=stub_test,
            )

    def add_spike_waveforms(
        self, nwbfile, ecephys_module, shank_number: int, shank_channels: list, conversion: float, stub_test: bool
    ):
        spk_file_path = self.session_path / f"{self.session_id}.spk.{shank_number}"
        res_file_path = self.session_path / f"{self.session_id}.res.{shank_number}"
        if not spk_file_path.is_file():
            return
        n_samples = self.xml_info["spikes_n_samples"]
        # .spk files are (spikes, samples, channels); SpikeEventSeries data is (spikes, channels, samples)
        waveforms = np.memmap(spk_file_path, dtype=np.int16, mode="r").reshape(-1, n_samples, len(shank_channels))
        waveforms = waveforms.transpose(0, 2, 1)
        spike_frames = np.loadtxt(res_file_path, dtype=np.int64, ndmin=1)
        if len(spike_frames) != len(waveforms):
            raise ValueError(f"{res_file_path} has {len(spike_frames)} spikes but {spk_file_path} has {len(waveforms)}")
        if stub_test:
            waveforms, spike_frames = waveforms[:STUB_SPIKES], spike_frames[:STUB_SPIKES]

        group = nwbfile.electrode_groups[f"shank{shank_number}"]
        # The .spk columns follow the order of the shank's channels in the xml file
        electrode_indices = [int(np.flatnonzero(self.channels == channel)[0]) for channel in shank_channels]
        ecephys_module.add(
            SpikeEventSeries(
                name=f"SpikeWaveforms{shank_number}",
                description=f"waveforms of all spikes detected on {group.name}, from the .spk.{shank_number} file",
                data=SliceableDataChunkIterator(data=waveforms),
                timestamps=spike_frames / self.xml_info["sampling_rate"],
                electrodes=nwbfile.create_electrode_table_region(
                    region=electrode_indices, description=f"{group.name} electrodes"
                ),
                conversion=conversion,
            )
        )
