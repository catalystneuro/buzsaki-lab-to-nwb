"""Units of a Fujisawa session (DANDI:000067), from the lab's .clu and .res files."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from neuroconv.tools.nwb_helpers import get_module
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
        if not any((self.session_path / f"{self.session_id}.clu.{shank}").is_file() for shank in [*PFC_SHANKS, *CA1_SHANKS]):
            self.add_uncurated_units(nwbfile, stub_test=stub_test)
            return
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

    def session_slice(self, day_samples: np.ndarray, samples: np.ndarray) -> tuple:
        """Index and sample offset of the session's spikes in the spikes of the whole day's recording."""
        n = len(samples)
        lead = min(n - 1, 50)
        day_diff, diff = np.diff(day_samples), np.diff(samples[: lead + 1])
        candidates = np.flatnonzero(day_diff[: len(day_samples) - n + 1] == diff[0]) if lead else np.arange(len(day_samples) - n + 1)
        for k in range(1, lead):
            candidates = candidates[day_diff[candidates + k] == diff[k]]
        for start in candidates:
            offset = day_samples[start] - samples[0]
            if np.array_equal(day_samples[start : start + n] - offset, samples):
                return int(start), int(offset)
        raise ValueError(f"{self.session_id}: spikes not found in the day's automatic clustering")

    def add_uncurated_units(self, nwbfile: NWBFile, stub_test: bool = False):
        """The session's spikes in the automatic clustering of the whole day's recording (the unsorted folder)."""
        day = self.session_path.parent.name
        unsorted = self.session_path.parent / "unsorted"
        shanks = [
            shank
            for shank in [*PFC_SHANKS, *CA1_SHANKS]
            if (unsorted / f"{day}.clu.{shank}").is_file() and (self.session_path / f"{self.session_id}.res.{shank}").is_file()
        ]
        if not shanks:
            return
        units = Units(
            name="uncurated_units",
            description=(
                f"UNCURATED automatic clusters. The lab did not sort the spikes of this session by hand. These units are "
                f"KlustaKwik's automatic clusters of the whole day's recording ({day}, in its 'unsorted' folder), cut to "
                f"this session: the clusters numbered 2 and up of {day}.clu.N, for the session's spikes in its "
                f"{self.session_id}.res.N files (20 kHz samples). Clusters 0 and 1 are left out. They have not been "
                f"checked by a person and may merge or split neurons; cluster numbers are those of the day's automatic "
                f"clustering and match no curated units (of the day's sessions only EE.049 was sorted by hand)."
            ),
            resolution=1 / SAMPLING_RATE,
        )
        units.add_column(name="shank", description="shank number (1 to 8 mPFC, 9 to 12 CA1)")
        units.add_column(name="cluster_id", description=f"cluster number in the automatic {day}.clu file of the shank")
        units.add_column(name="region", description="region of the shank: mPFC or CA1")
        groups = nwbfile.electrode_groups
        for shank in shanks:
            samples = np.loadtxt(self.session_path / f"{self.session_id}.res.{shank}", dtype=np.int64, ndmin=1)
            if len(samples) == 0:
                continue
            day_clusters = np.loadtxt(unsorted / f"{day}.clu.{shank}", dtype=np.int64, ndmin=1)[1:]
            day_samples = np.loadtxt(unsorted / f"{day}.res.{shank}", dtype=np.int64, ndmin=1)
            if len(day_clusters) != len(day_samples):
                raise ValueError(f"{day} shank {shank}: {len(day_clusters)} clusters for {len(day_samples)} spikes")
            start, _ = self.session_slice(day_samples, samples)
            clusters = day_clusters[start : start + len(samples)]
            for cluster in np.unique(clusters[clusters >= 2]):
                units.add_unit(
                    spike_times=np.sort(samples[clusters == cluster]) / SAMPLING_RATE,
                    electrode_group=groups[f"shank{shank}"],
                    shank=shank,
                    cluster_id=int(cluster),
                    region=region_of_shank(shank),
                )
                if stub_test and len(units) >= STUB_UNITS:
                    break
        if len(units):
            get_module(nwbfile, "ecephys", "processed extracellular electrophysiology data").add(units)
