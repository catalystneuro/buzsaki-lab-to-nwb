"""Authors: Cody Baker and Ben Dichter."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.misc import Units

from .watsonutils import read_session_xml

CELL_TYPES = {"pE": "excitatory", "pI": "inhibitory"}
STUB_SPIKES = 100


class WatsonSortingInterface(BaseDataInterface):
    """Units of a Watson session.

    Units are the clusters numbered 2 and up in the .clu.N files (0 is noise and 1 is multi-unit activity), with
    spike times from the matching .res.N files. Their cell type, region and global id come from the entry with the
    same shank and cluster in .spikes.cellinfo.mat and .CellClass.cellinfo.mat; units without one are marked
    "unknown". When the session has no .clu files, the units and spike times (in seconds) are those of
    .spikes.cellinfo.mat.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")

    def read_cell_info(self) -> dict:
        """Map (shank, cluster) to the unit's entry in the buzcode cellinfo files."""
        spikes = read_mat(str(self.session_path / f"{self.session_id}.spikes.cellinfo.mat"))["spikes"]
        cell_class_file_path = self.session_path / f"{self.session_id}.CellClass.cellinfo.mat"
        labels = read_mat(str(cell_class_file_path))["CellClass"]["label"] if cell_class_file_path.is_file() else []
        if len(labels) and len(labels) != len(spikes["UID"]):
            raise ValueError(f"{cell_class_file_path} has {len(labels)} labels for {len(spikes['UID'])} units")

        cell_info = {}
        for index, (shank, cluster) in enumerate(zip(spikes["shankID"], spikes["cluID"])):
            cell_info[(int(shank), int(cluster))] = dict(
                global_id=int(spikes["UID"][index]),
                region=str(spikes["region"][index]),
                cell_type=CELL_TYPES[labels[index]] if len(labels) else "unknown",
                times=np.atleast_1d(spikes["times"][index]),
            )
        return cell_info

    def read_clustered_units(self) -> dict:
        """Map (shank, cluster) to spike times in seconds for the clusters numbered 2 and up in the .clu files."""
        units = {}
        for shank_index, _ in enumerate(self.xml_info["shank_channels"]):
            shank = shank_index + 1
            clu_file_path = self.session_path / f"{self.session_id}.clu.{shank}"
            if not clu_file_path.is_file():
                continue
            clusters = np.loadtxt(clu_file_path, dtype=np.int64)[1:]  # the first line is the number of clusters
            frames = np.loadtxt(self.session_path / f"{self.session_id}.res.{shank}", dtype=np.int64, ndmin=1)
            for cluster in np.unique(clusters[clusters > 1]):
                units[(shank, int(cluster))] = frames[clusters == cluster] / self.xml_info["sampling_rate"]
        return units

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        cell_info = self.read_cell_info()
        units = self.read_clustered_units()
        if not units:
            units = {key: info["times"] for key, info in cell_info.items()}

        nwbfile.units = Units(
            name="units",
            description="sorted single units",
            resolution=1 / self.xml_info["sampling_rate"],
        )
        nwbfile.add_unit_column(name="global_id", description="global id of the cell for the entire experiment")
        nwbfile.add_unit_column(name="shank", description="1-indexed shank the unit was detected on")
        nwbfile.add_unit_column(name="cluster_id", description="cluster number in the .clu file of the shank")
        nwbfile.add_unit_column(
            name="cell_type",
            description=(
                "putative cell type from CellClass.cellinfo.mat (pE: excitatory, pI: inhibitory); "
                "'unknown' for units in the clu files that are not in CellClass.cellinfo.mat"
            ),
        )
        nwbfile.add_unit_column(
            name="region",
            description=(
                "brain region where unit was detected, from spikes.cellinfo.mat; "
                "'unknown' for units in the clu files that are not in spikes.cellinfo.mat"
            ),
        )
        missing = dict(global_id=-1, region="unknown", cell_type="unknown")
        for (shank, cluster), spike_times in sorted(units.items()):
            info = cell_info.get((shank, cluster), missing)
            group = nwbfile.electrode_groups[f"shank{shank}"]
            electrodes = [index for index, name in enumerate(nwbfile.electrodes["group_name"][:]) if name == group.name]
            nwbfile.add_unit(
                spike_times=spike_times[:STUB_SPIKES] if stub_test else spike_times,
                electrode_group=group,
                electrodes=electrodes,
                global_id=info["global_id"],
                shank=shank,
                cluster_id=cluster,
                cell_type=info["cell_type"],
                region=info["region"],
            )
