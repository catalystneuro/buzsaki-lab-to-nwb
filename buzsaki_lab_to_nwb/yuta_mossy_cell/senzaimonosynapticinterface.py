"""Curated monosynaptic connections and zero-lag synchrony of a Senzai session (DANDI:000003)."""

import numpy as np
from hdmf.common import DynamicTable, DynamicTableRegion
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import FilePath
from pynwb import NWBFile
from scipy.io import loadmat


def unit_pairs(mat: dict, name: str) -> np.ndarray:
    """(n, 4) rows of (first shank, first cluster, second shank, second cluster); empty when there are none."""
    values = np.asarray(mat[name]).ravel()
    return values.reshape(-1, 4) if values.size else np.empty((0, 4), dtype=int)


class SenzaiMonosynapticInterface(BaseDataInterface):
    """Pairs from the lab's MonoSynConvClick.mat: putative monosynaptic connections and zero-lag synchronous pairs."""

    def __init__(self, file_path: FilePath, verbose: bool = False):
        super().__init__(file_path=file_path, verbose=verbose)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        mat = loadmat(str(self.source_data["file_path"]), squeeze_me=True)
        units = nwbfile.units
        row_of = {
            (int(shank), int(cluster)): row
            for row, (shank, cluster) in enumerate(zip(units["shank"][:], units["cluster_id"][:]))
        }
        module = get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data")

        def unit_region(name, description, rows):
            return DynamicTableRegion(
                name=name, description=description, data=np.asarray(rows, dtype=np.int64), table=units
            )

        connections = []
        for kind, name in (("excitatory", "FinalExcMonoSyn"), ("inhibitory", "FinalInhMonoSyn")):
            for pre_shank, pre_cluster, post_shank, post_cluster in unit_pairs(mat, name):
                pre, post = (pre_shank, pre_cluster), (post_shank, post_cluster)
                if pre in row_of and post in row_of:  # a stub conversion keeps only some units
                    connections.append((row_of[pre], row_of[post], kind))
        # Empty tables are left out
        if connections:
            table = DynamicTable(
                name="monosynaptic_connections",
                description=(
                    "putative monosynaptic connections from the authors' MonoSynConvClick.mat: narrow significant peaks "
                    "(excitatory) or troughs (inhibitory) at latencies under 5 ms in the spike cross-correlogram of the "
                    "presynaptic unit and the postsynaptic unit"
                ),
                columns=[
                    unit_region("presynaptic_unit", "the presynaptic unit", [pre for pre, _, _ in connections]),
                    unit_region("postsynaptic_unit", "the postsynaptic unit", [post for _, post, _ in connections]),
                ],
            )
            table.add_column(
                name="connection",
                description="excitatory or inhibitory",
                data=np.asarray([kind for _, _, kind in connections], dtype=str),
            )
            module.add(table)

        pairs = [
            (row_of[(shank_1, cluster_1)], row_of[(shank_2, cluster_2)])
            for shank_1, cluster_1, shank_2, cluster_2 in unit_pairs(mat, "FinalpureZeroLag")
            if (shank_1, cluster_1) in row_of and (shank_2, cluster_2) in row_of
        ]
        if pairs:
            module.add(
                DynamicTable(
                    name="zero_lag_synchrony",
                    description=(
                        "pairs of units with a narrow large peak at under 1 ms latency in their spike cross-correlogram "
                        "('zero time lag' pairs), from FinalpureZeroLag of the authors' MonoSynConvClick.mat"
                    ),
                    columns=[
                        unit_region("unit_1", "first unit of the pair", [first for first, _ in pairs]),
                        unit_region("unit_2", "second unit of the pair", [second for _, second in pairs]),
                    ],
                )
            )
