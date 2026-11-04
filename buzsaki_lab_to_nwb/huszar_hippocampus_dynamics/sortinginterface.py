"""Units of a Huszar session (DANDI:000552) from spikes.cellinfo.mat and, where present, cell_metrics.cellinfo.mat."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.misc import Units

from .huszarutils import read_session

# cell_metrics fields written as unit columns: name in the file, column name, description
CELL_METRICS_COLUMNS = (
    (
        "putativeCellType",
        "putative_cell_type",
        "CellExplorer putative cell type (cell_metrics.putativeCellType), from the trough-to-peak time and the "
        "autocorrelogram",
    ),
    ("troughToPeak", "trough_to_peak", "trough-to-peak time of the mean waveform, in ms (cell_metrics.troughToPeak)"),
    (
        "acg_tau_rise",
        "acg_tau_rise",
        "rise time constant of the autocorrelogram fit, in ms (cell_metrics.acg_tau_rise)",
    ),
    ("firingRate", "firing_rate", "mean firing rate over the session, in Hz (cell_metrics.firingRate)"),
)
OPTO_TAG_COLUMNS = (
    (
        "p_salt",
        "opto_p_salt",
        "p value of the stimulus-associated spike latency test (SALT) for the light pulses (cell_metrics.optoTag.p_salt)",
    ),
    (
        "h_reliable",
        "opto_h_reliable",
        "True if the lab's test marked the unit's light response as reliable (cell_metrics.optoTag.h_reliable); the "
        "criterion the paper used to call a unit light-responsive (birthdated) is not stated in the source",
    ),
    (
        "int_ratemod",
        "opto_int_ratemod",
        "firing rate modulation during the light pulse periods (cell_metrics.optoTag.int_ratemod); NaN where the lab "
        "did not compute it",
    ),
    (
        "int_ratemod_pval",
        "opto_int_ratemod_pval",
        "p value of the firing rate modulation during the light pulse periods (cell_metrics.optoTag.int_ratemod_pval)",
    ),
)


class HuszarSortingInterface(BaseDataInterface):
    """Kilosort units, manually curated in Phy, with spike times and mean waveforms from spikes.cellinfo.mat."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def read_cell_metrics(self, spikes: dict):
        file_path = self.session_path / f"{self.session_id}.cell_metrics.cellinfo.mat"
        if not file_path.is_file():
            return None
        cell_metrics = read_mat(file_path)["cell_metrics"]
        if not np.array_equal(np.atleast_1d(cell_metrics["UID"]), np.atleast_1d(spikes["UID"])):
            raise ValueError(f"The units of cell_metrics and spikes.cellinfo of {self.session_id} differ")
        if not all(
            np.array_equal(np.atleast_1d(a), np.atleast_1d(b))
            for a, b in zip(cell_metrics["spikes"]["times"], spikes["times"])
        ):
            raise ValueError(f"The spike times of cell_metrics and spikes.cellinfo of {self.session_id} differ")
        return cell_metrics

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        spikes = read_mat(self.session_path / f"{self.session_id}.spikes.cellinfo.mat")["spikes"]
        cell_metrics = self.read_cell_metrics(spikes)
        session = read_session(self.session_path)
        sampling_rate = float(session["extracellular"]["sr"])
        n_units = int(spikes["numcells"])
        params = spikes.get("processinginfo", {}).get("params", {})
        filter_band = params.get("WaveformsFiltFreq", [500, 8000])
        n_pulled = params.get("Waveforms_nPull", "")

        channels = [np.atleast_1d(channels).astype(int) - 1 for channels in spikes["channels_all"]]
        waveforms = [np.asarray(waveform, dtype=float) for waveform in spikes["filtWaveform_all"]]
        same_channels = all(np.array_equal(channels[0], unit_channels) for unit_channels in channels)

        nwbfile.units = Units(
            name="units",
            description=(
                "units sorted with KiloSort and curated in Phy (session.mat spikeSorting), from the lab's "
                "spikes.cellinfo.mat; waveform_mean is the lab's mean filtered waveform (filtWaveform_all: "
                f"{filter_band[0]} to {filter_band[1]} Hz, mean of {n_pulled} spikes) on every channel, in electrode "
                "order of the electrodes column, converted from uV to volts"
            ),
            resolution=1 / sampling_rate,
            waveform_rate=sampling_rate,
            waveform_unit="volts",
            electrode_table=nwbfile.electrodes,
        )
        nwbfile.add_unit_column(name="unit_name", description="UID of the unit in the lab's files")
        nwbfile.add_unit_column(name="cluster_id", description="Phy cluster id of the unit (spikes.cellinfo cluID)")
        nwbfile.add_unit_column(
            name="shank_id", description="1-indexed electrode group the unit was sorted on (spikes.cellinfo shankID)"
        )
        nwbfile.add_unit_column(
            name="max_electrode",
            description="electrode with the largest waveform (spikes.cellinfo maxWaveformCh)",
            table=nwbfile.electrodes,
        )
        if cell_metrics is not None:
            for _, column, description in CELL_METRICS_COLUMNS:
                nwbfile.add_unit_column(name=column, description=description)
            for _, column, description in OPTO_TAG_COLUMNS:
                nwbfile.add_unit_column(name=column, description=description)

        for index in range(n_units):
            group = nwbfile.electrode_groups[f"Group {int(spikes['shankID'][index])}"]
            row = dict(
                spike_times=np.atleast_1d(spikes["times"][index]).astype(float),
                electrode_group=group,
                electrodes=list(channels[index]),
                unit_name=str(int(spikes["UID"][index])),
                cluster_id=int(spikes["cluID"][index]),
                shank_id=int(spikes["shankID"][index]),
                max_electrode=int(spikes["maxWaveformCh"][index]),
            )
            if same_channels:
                # Samples by channels, in volts
                row["waveform_mean"] = (waveforms[index].T * 1e-6).astype(np.float32)
            if cell_metrics is not None:
                for field, column, _ in CELL_METRICS_COLUMNS:
                    value = cell_metrics[field][index]
                    row[column] = str(value) if isinstance(value, str) else float(value)
                for field, column, _ in OPTO_TAG_COLUMNS:
                    value = float(cell_metrics["optoTag"][field][index])
                    row[column] = bool(value) if field == "h_reliable" else value
            nwbfile.add_unit(**row)
