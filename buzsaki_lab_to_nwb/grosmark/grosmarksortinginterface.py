"""Units of a Grosmark session (DANDI:000044)."""

from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.misc import Units

from .grosmarkutils import read_sess_info, read_session_xml

STUB_UNITS = 5
CELL_TYPES = {"pyramidal": "pyramidal cell", "interneuron": "interneuron"}


class GrosmarkSortingInterface(BaseDataInterface):
    """Units from the lab's sessInfo.Spikes: spike times, cluster IDs (spike group x 100 + cluster) and the putative
    pyramidal cells and interneurons (PyrIDs, IntIDs).

    When the session's .clu and .res files are given, each unit's spikes are checked to be the spikes of its cluster.
    """

    def __init__(self, folder_path: DirectoryPath, clu_res_folder_path: Optional[DirectoryPath] = None, verbose=False):
        super().__init__(folder_path=folder_path, clu_res_folder_path=clu_res_folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")

    def read_units(self) -> dict:
        """Map each cluster ID to its spike times in seconds, in ID order."""
        sess_info = read_sess_info(self.session_path / f"{self.session_id}_sessInfo.mat")
        self.pyramidal_ids = set(sess_info["pyramidal_ids"])
        self.interneuron_ids = set(sess_info["interneuron_ids"])
        times, ids = sess_info["spike_times"], sess_info["spike_ids"]
        order = np.argsort(ids, kind="stable")
        unit_ids, starts = np.unique(ids[order], return_index=True)
        units = {int(unit_id): np.sort(chunk) for unit_id, chunk in zip(unit_ids, np.split(times[order], starts[1:]))}
        self.check_against_clu_res(units)
        return units

    def check_against_clu_res(self, units: dict):
        folder_path = self.source_data["clu_res_folder_path"]
        if folder_path is None:
            return
        sampling_rate = self.xml_info["sampling_rate"]
        for spike_group in sorted({unit_id // 100 for unit_id in units}):
            clusters = np.loadtxt(Path(folder_path) / f"{self.session_id}.clu.{spike_group}", dtype=np.int64)[1:]
            samples = np.loadtxt(Path(folder_path) / f"{self.session_id}.res.{spike_group}", dtype=np.int64)
            for unit_id, unit_times in units.items():
                if unit_id // 100 != spike_group:
                    continue
                unit_samples = np.rint(unit_times * sampling_rate).astype(np.int64)
                if not np.array_equal(unit_samples, samples[clusters == unit_id % 100]):
                    raise ValueError(f"Unit {unit_id} of {self.session_id} is not cluster {unit_id % 100} of its .clu")

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        units = self.read_units()
        if stub_test:
            units = dict(list(units.items())[:STUB_UNITS])
        sampling_rate = self.xml_info["sampling_rate"]
        nwbfile.units = Units(
            name="units",
            description=(
                "putative single units, sorted within each shank by automatic clustering of PCA features of the 20 kHz "
                "wide-band signal and manual curation (clusters 2 and up of the .clu files; CRCNS hc-11 description), from the lab's sessInfo.Spikes. The "
                "unit ids are the lab's SpikeIDs (spike group x 100 + cluster). Spike times are seconds into the concatenated PRE, MAZE and POST recording."
            ),
            resolution=1 / sampling_rate,
        )
        nwbfile.add_unit_column(
            name="spike_group", description="1-based spike group (shank) of the unit: floor(sessInfo SpikeID / 100)"
        )
        nwbfile.add_unit_column(
            name="cluster_id", description="cluster number in the spike group's .clu file: sessInfo SpikeID mod 100"
        )
        nwbfile.add_unit_column(
            name="cell_type",
            description=(
                "putative cell type from the lab's sessInfo.Spikes.PyrIDs and IntIDs, 'pyramidal cell' or "
                "'interneuron', determined from cross-correlograms, spike width and after-hyperpolarization"
            ),
        )
        nwbfile.add_unit_column(name="hemisphere", description="hemisphere of the unit's probe: left or right")

        spike_groups = list(nwbfile.electrodes["spike_group"][:])
        for unit_id, spike_times in units.items():
            spike_group = unit_id // 100
            if unit_id in self.pyramidal_ids:
                cell_type = CELL_TYPES["pyramidal"]
            elif unit_id in self.interneuron_ids:
                cell_type = CELL_TYPES["interneuron"]
            else:
                cell_type = "unclassified"
            electrodes = [row for row, value in enumerate(spike_groups) if value == spike_group]
            group = nwbfile.electrode_groups[nwbfile.electrodes["group_name"][electrodes[0]]]
            nwbfile.add_unit(
                id=unit_id,
                spike_times=spike_times,
                electrode_group=group,
                electrodes=electrodes,
                spike_group=spike_group,
                cluster_id=unit_id % 100,
                cell_type=cell_type,
                hemisphere=nwbfile.electrodes["hemisphere"][electrodes[0]],
            )
