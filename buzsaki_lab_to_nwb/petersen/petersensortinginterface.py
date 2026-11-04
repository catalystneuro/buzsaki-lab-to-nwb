"""Units of a Petersen session (DANDI:000059): the Phy clusters of the session's Kilosort folder."""

import re
from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.misc import Units

from .petersenutils import read_mat, read_phy_labels, read_session_xml

STUB_UNITS = 5

UNITS_DESCRIPTION = (
    "All clusters of the session's Phy folder ({folder}), sorted with KiloSort and curated by the lab in Phy. The "
    "curated cells, the cell set of the paper, are the units with quality 'good': they are the units in the lab's "
    "CellExplorer file ({cell_metrics}), which gives their cell type and region. Units with quality 'noise' are "
    "clusters the lab rejected. Spike times are the Phy spike samples ({sampling_rate:g} Hz) in seconds, sorted."
)


class PetersenSortingInterface(BaseDataInterface):
    """Units from spike_times.npy and spike_clusters.npy, with the Phy labels and the CellExplorer cell metrics."""

    def __init__(self, folder_path: DirectoryPath, phy_folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, phy_folder_path=phy_folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.phy_path = Path(phy_folder_path)
        self.sampling_rate = read_session_xml(self.session_path / f"{self.session_id}.xml")["sampling_rate"]
        sample_rate = re.search(r"^sample_rate\s*=\s*([\d.eE+-]+)", (self.phy_path / "params.py").read_text(), re.M)
        if sample_rate is None or float(sample_rate.group(1)) != self.sampling_rate:
            raise ValueError(f"params.py and the .xml of {self.session_id} give different sampling rates")

    def read_units(self) -> dict:
        """Map each Phy cluster id to its spike samples (sorted) and the amplitudes of those spikes."""
        spike_samples = np.load(self.phy_path / "spike_times.npy").ravel().astype(np.int64)
        spike_clusters = np.load(self.phy_path / "spike_clusters.npy").ravel().astype(np.int64)
        amplitudes_path = self.phy_path / "amplitudes.npy"
        amplitudes = np.load(amplitudes_path).ravel() if amplitudes_path.is_file() else None
        if len(spike_samples) != len(spike_clusters) or (
            amplitudes is not None and len(amplitudes) != len(spike_samples)
        ):
            raise ValueError(f"The Phy files of {self.session_id} have different numbers of spikes")
        order = np.lexsort((spike_samples, spike_clusters))  # by cluster, then time
        spike_samples, spike_clusters = spike_samples[order], spike_clusters[order]
        if amplitudes is not None:
            amplitudes = amplitudes[order]
        cluster_ids, starts = np.unique(spike_clusters, return_index=True)
        stops = np.append(starts[1:], len(spike_clusters))
        return {
            int(cluster): (
                spike_samples[start:stop],
                amplitudes[start:stop] if amplitudes is not None else None,
            )
            for cluster, start, stop in zip(cluster_ids, starts, stops)
        }

    def read_cell_metrics(self) -> dict:
        """Map Phy cluster id (cluID) to the CellExplorer entry of the cell."""
        file_path = self.session_path / f"{self.session_id}.cell_metrics.cellinfo.mat"
        if not file_path.is_file():
            return {}
        metrics = read_mat(file_path)["cell_metrics"]
        cells = {}
        for index, cluster in enumerate(np.atleast_1d(metrics["cluID"])):
            cells[int(cluster)] = dict(
                cell_type=str(np.atleast_1d(metrics["putativeCellType"])[index]),
                brain_region=str(np.atleast_1d(metrics["brainRegion"])[index]),
                cell_metrics_id=int(np.atleast_1d(metrics["cellID"])[index]),
                max_waveform_channel=int(np.atleast_1d(metrics["maxWaveformCh"])[index]),
                spike_count=int(np.atleast_1d(metrics["spikeCount"])[index]),
            )
        return cells

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        units = self.read_units()
        labels, label_file = read_phy_labels(self.phy_path)
        cells = self.read_cell_metrics()
        missing = set(cells) - set(units)
        if missing:
            raise ValueError(f"cell_metrics of {self.session_id} lists clusters {sorted(missing)} without spikes")
        for cluster, cell in cells.items():
            if len(units[cluster][0]) != cell["spike_count"]:
                raise ValueError(f"Cluster {cluster} of {self.session_id} has another spike count in cell_metrics")
        if stub_test:
            units = dict(list(units.items())[:STUB_UNITS])

        has_amplitudes = any(amplitudes is not None for _, amplitudes in units.values())
        nwbfile.units = Units(
            name="units",
            description=UNITS_DESCRIPTION.format(
                folder=self.phy_path.name,
                cell_metrics=f"{self.session_id}.cell_metrics.cellinfo.mat",
                sampling_rate=self.sampling_rate,
            ),
            resolution=1 / self.sampling_rate,
        )
        nwbfile.add_unit_column(name="cluster_id", description="cluster id in the Phy folder")
        nwbfile.add_unit_column(
            name="quality",
            description=(
                f"Phy label of the cluster ({label_file or 'no label file'}): 'good' for the curated cells, 'noise' for "
                "rejected clusters, 'mua' for multi-unit activity; 'unsorted' for clusters without a label (Phy's "
                "default); other labels (such as 'good2') are the lab's and not described in the source"
            ),
        )
        nwbfile.add_unit_column(
            name="cell_type",
            description=(
                "putative cell type in the lab's CellExplorer file (putativeCellType); empty for units not in that file"
            ),
        )
        nwbfile.add_unit_column(
            name="region",
            description="brain region in the lab's CellExplorer file (brainRegion); empty for units not in that file",
        )
        nwbfile.add_unit_column(
            name="cell_metrics_id",
            description="cellID of the unit in the lab's CellExplorer file; -1 for units not in that file",
        )
        nwbfile.add_unit_column(
            name="max_waveform_channel",
            description=(
                "0-based channel with the largest waveform, from the lab's CellExplorer file (maxWaveformCh); -1 for "
                "units not in that file"
            ),
        )
        if has_amplitudes:
            nwbfile.add_unit_column(
                name="amplitudes",
                description="KiloSort template amplitude (scaling) of each spike, from amplitudes.npy, in spike order",
                index=True,
            )
        for cluster, (samples, amplitudes) in units.items():
            cell = cells.get(cluster, {})
            row = dict(
                spike_times=samples / self.sampling_rate,
                id=cluster,
                cluster_id=cluster,
                quality=str(labels.get(cluster, "unsorted")),
                cell_type=cell.get("cell_type", ""),
                region=cell.get("brain_region", ""),
                cell_metrics_id=cell.get("cell_metrics_id", -1),
                max_waveform_channel=cell.get("max_waveform_channel", -1),
            )
            if has_amplitudes:
                row["amplitudes"] = amplitudes.astype(np.float32)
            nwbfile.add_unit(**row)
