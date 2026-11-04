"""Units of a Fujisawa session (DANDI:000067), from the lab's .clu and .res files."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.misc import Units
from scipy.io import loadmat

from .fujisawautils import CA1_SHANKS, PFC_SHANKS, behavior_files, read_clusters, region_of_shank

SAMPLING_RATE = 20_000.0
CELL_TYPES = {1: "pyramidal cell", 2: "interneuron", 3: "unknown"}
STUB_UNITS = 10


class FujisawaSortingInterface(BaseDataInterface):
    """Units: the clusters numbered 2 and up of the .clu files of the probe shanks (1 to 12), with spike times from the
    .res files.

    Clusters 0 (artifacts) and 1 (noise and multi-unit activity) are left out, as are the clusters of the 13th channel
    group, which holds the non-neural inputs. Where the session has the lab's per-region behavior files, their
    `CellsInfo` gives the cell type of the units the paper used, matched to clusters through `spikeph`.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def read_cell_info(self) -> dict:
        """(shank, cluster): (cell number, cell type) from the per-region behavior files."""
        info = {}
        files = behavior_files(self.session_path)
        for region, shanks in (("mPFC", PFC_SHANKS), ("CA1", CA1_SHANKS)):
            if region not in files:
                continue
            mat = loadmat(str(files[region]), variable_names=["spikeph", "CellsInfo"])
            cell_types = {int(cell): int(cell_type) for cell, _, cell_type in mat["CellsInfo"]}
            for cell, shank, cluster in mat["spikeph"].astype(int):
                # The CA1 file numbers the CA1 shanks from 1
                key = (int(shank) + shanks.start - 1, int(cluster))
                info[key] = (int(cell), CELL_TYPES[cell_types[cell]] if cell in cell_types else "not used in the paper")
        return info

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        cell_info = self.read_cell_info()
        has_cell_types = bool(cell_info)
        nwbfile.units = Units(
            name="units",
            description=(
                "Units sorted by the lab: the clusters numbered 2 and up of the .clu files of shanks 1 to 12, with "
                "spike times from the .res files (20 kHz samples). Clusters 0 and 1 (artifacts, noise and multi-unit "
                "activity) are left out."
            ),
            resolution=1 / SAMPLING_RATE,
        )
        nwbfile.add_unit_column(name="shank", description="shank number (1 to 8 mPFC, 9 to 12 CA1)")
        nwbfile.add_unit_column(name="cluster_id", description="cluster number in the .clu file of the shank")
        nwbfile.add_unit_column(name="region", description="region of the shank: mPFC or CA1")
        nwbfile.add_unit_column(
            name="cell_type",
            description=(
                "cell type of the lab's CellsInfo (pyramidal cell, interneuron or unknown) for the units the paper used; "
                "'not used in the paper' for other units of the lab's cell list, 'not classified in the source' where "
                "the session has no per-region behavior files"
            ),
        )
        nwbfile.add_unit_column(
            name="lab_cell_number",
            description="cell number of the unit in the lab's behavior files (spikeind), -1 if it has none",
        )
        groups = nwbfile.electrode_groups
        for shank in [*PFC_SHANKS, *CA1_SHANKS]:
            if not (self.session_path / f"{self.session_id}.clu.{shank}").is_file():
                continue
            clusters, samples = read_clusters(self.session_path, shank)
            for cluster in np.unique(clusters[clusters >= 2]):
                cell, cell_type = cell_info.get(
                    (shank, int(cluster)),
                    (-1, "not used in the paper" if has_cell_types else "not classified in the source"),
                )
                nwbfile.add_unit(
                    spike_times=np.sort(samples[clusters == cluster]) / SAMPLING_RATE,
                    electrode_group=groups[f"shank{shank}"],
                    shank=shank,
                    cluster_id=int(cluster),
                    region=region_of_shank(shank),
                    cell_type=cell_type,
                    lab_cell_number=cell,
                )
                if stub_test and len(nwbfile.units) >= STUB_UNITS:
                    return
