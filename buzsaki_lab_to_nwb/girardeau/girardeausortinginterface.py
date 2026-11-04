"""Units of a Girardeau session (DANDI:000061), from the lab's .clu and .res files."""

from pathlib import Path

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.misc import Units

from .girardeauutils import (
    UNKNOWN_REGION,
    describe_region_codes,
    load_mat,
    read_recording_locations,
    read_session_xml,
)

STUB_UNITS = 10


def read_clusters(session_path: Path, shank: int) -> tuple:
    """Cluster of each spike (the first line of the .clu file is the number of clusters) and its time in samples."""
    session_id = session_path.name
    clusters = np.loadtxt(session_path / f"{session_id}.clu.{shank}", dtype=np.int64, ndmin=1)[1:]
    samples = np.loadtxt(session_path / f"{session_id}.res.{shank}", dtype=np.int64, ndmin=1)
    if len(clusters) != len(samples):
        raise ValueError(f"{session_id} shank {shank}: {len(clusters)} clusters for {len(samples)} spikes")
    return clusters, samples


def read_cellinfo(file_path: Path) -> tuple:
    """(shank, cluster) keys, spike times (s) and region labels of a buzcode spikes.cellinfo.mat (v5 or v7.3)."""
    try:
        spikes = load_mat(file_path)["spikes"]
        keys = [(int(s), int(c)) for s, c in zip(np.atleast_1d(spikes.shankID), np.atleast_1d(spikes.cluID))]
        trains = [np.atleast_1d(times) for times in np.atleast_1d(spikes.times)]
        regions = [str(region) for region in np.atleast_1d(getattr(spikes, "region", []))]
    except NotImplementedError:  # MATLAB v7.3
        with h5py.File(file_path, "r") as mat:
            spikes = mat["spikes"]
            keys = [(int(s), int(c)) for s, c in zip(spikes["shankID"][:].ravel(), spikes["cluID"][:].ravel())]
            trains = [np.asarray(mat[ref]).ravel() for ref in spikes["times"][:].ravel()]
            regions = []
            if "region" in spikes:
                regions = ["".join(map(chr, np.asarray(mat[ref]).ravel())) for ref in spikes["region"][:].ravel()]
    return keys, trains, regions


class GirardeauSortingInterface(BaseDataInterface):
    """Units: the clusters numbered 2 and up of the .clu.N files, with spike times from the .res.N files.

    Clusters 0 (artifacts) and 1 (noise and multi-unit activity) are left out. Where the session has the lab's 2020
    buzcode spikes.cellinfo.mat, each of its units is checked to be the cluster with the same shank and cluster number.
    """

    def __init__(self, folder_path: DirectoryPath, subject_folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, subject_folder_path=subject_folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.regions = read_recording_locations(Path(subject_folder_path), self.session_id)

    def read_units(self) -> dict:
        """(shank, cluster) -> sorted spike times in samples, in shank and cluster order."""
        units = {}
        for shank in range(1, len(self.xml_info["spike_groups"]) + 1):
            if not (self.session_path / f"{self.session_id}.clu.{shank}").is_file():
                continue
            clusters, samples = read_clusters(self.session_path, shank)
            for cluster in np.unique(clusters[clusters >= 2]):
                units[(shank, int(cluster))] = np.sort(samples[clusters == cluster])
        return units

    def check_cellinfo(self, units: dict) -> str:
        """Check the units of spikes.cellinfo.mat against the clusters; return a note for the table description."""
        cellinfo_file_path = self.session_path / f"{self.session_id}.spikes.cellinfo.mat"
        if not cellinfo_file_path.is_file():
            return ""
        keys, trains, regions = read_cellinfo(cellinfo_file_path)
        sampling_rate = self.xml_info["sampling_rate"]
        for key, times in zip(keys, trains):
            if key not in units or not np.allclose(
                np.sort(np.atleast_1d(times)), units[key] / sampling_rate, atol=0.6 / sampling_rate
            ):
                raise ValueError(f"{self.session_id}: the spikes.cellinfo.mat unit {key} is not its cluster")
        note = (
            f" The {len(keys)} units of the lab's spikes.cellinfo.mat are the clusters with the same shank and cluster "
            "number, spike for spike (checked)."
        )
        if regions:
            # The buzcode region labels, compared with RecordingLocations.mat
            differ = sorted(
                {
                    (key[0], region)
                    for key, region in zip(keys, regions)
                    if region.lower() not in [code.lower() for code in self.regions.get(key[0], [])]
                }
            )
            if differ:
                note += (
                    " Its region labels differ from RecordingLocations.mat on shanks "
                    + ", ".join(f"{shank} ('{region}')" for shank, region in differ)
                    + "."
                )
            else:
                note += " Its region labels agree with RecordingLocations.mat, up to case."
        return note

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        units = self.read_units()
        note = self.check_cellinfo(units)
        sampling_rate = self.xml_info["sampling_rate"]
        shanks_with_units = sorted({shank for shank, _ in units})
        codes = {code for shank in shanks_with_units for code in self.regions.get(shank, [])}
        nwbfile.units = Units(
            name="units",
            description=(
                "Units sorted by the lab with KlustaKwik and curated in Klusters: the clusters numbered 2 and up of the "
                f".clu.N files, with spike times from the .res.N files ({sampling_rate:g} Hz samples). Clusters 0 "
                "(artifacts) and 1 (noise and multi-unit activity) are left out. Shanks with no .clu/.res files on the "
                "lab's share have no units." + note
            ),
            resolution=1 / sampling_rate,
        )
        nwbfile.add_unit_column(name="shank", description="shank number, the N of the unit's .clu.N/.res.N files")
        nwbfile.add_unit_column(name="cluster_id", description="cluster number in the .clu file of the shank")
        nwbfile.add_unit_column(
            name="region",
            description=(
                "the lab's region code of the unit's shank in RecordingLocations.mat (shankInfo), unchanged; 'unknown' "
                "for shanks the file does not place. Which codes make up the paper's 'BLA' is not stated in the "
                "source. Codes (Paxinos and Watson abbreviations, not confirmed by the lab): "
                + describe_region_codes(codes)
            ),
        )
        channel_ids = list(nwbfile.electrodes["channel_id"][:])
        for (shank, cluster), samples in units.items():
            nwbfile.add_unit(
                spike_times=samples / sampling_rate,
                electrode_group=nwbfile.electrode_groups[f"shank{shank}"],
                electrodes=[channel_ids.index(channel) for channel in self.xml_info["spike_groups"][shank - 1]],
                shank=shank,
                cluster_id=cluster,
                region="/".join(self.regions.get(shank, [])) or UNKNOWN_REGION,
            )
            if stub_test and len(nwbfile.units) >= STUB_UNITS:
                return
