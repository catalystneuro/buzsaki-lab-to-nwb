"""Units of a Peyrache session (DANDI:000056), from the lab's .clu and .res files."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.misc import Units

from .peyracheutils import (
    REGION_LOCATIONS,
    SAMPLING_RATE,
    TS_PER_SECOND,
    load_mat,
    read_session_xml,
    read_shank_structure,
)

STUB_UNITS = 10
CELL_CLASSES = {"pE": "putative excitatory", "pI": "putative inhibitory"}
HD_COLUMNS = {
    "hd_preferred_direction": (
        "preferred head direction (radians, in the frame of the head direction series) of the lab's FindHDCells "
        "(HDCells.mat hdCellStats column 1: the mean angle of the von Mises fit of the tuning curve during the "
        "open-field epoch, restricted to movement); NaN for units not in the lab's cell list"
    ),
    "hd_p_value": "p-value of the lab's test of head-direction tuning (hdCellStats column 2); NaN if not computed",
    "hd_kappa": "concentration (kappa) of the von Mises fit of the tuning curve (hdCellStats column 3); NaN if not computed",
    "hd_peak_rate": "peak firing rate of the tuning curve, in Hz (hdCellStats column 4); NaN if not computed",
}
QUALITY_COLUMNS = {
    "lratio": "L-ratio of the cluster (GeneralInfo.mat lratio, from the lab's calcClusterQuality on the .fet features)",
    "mahalanobis_distance": "isolation distance of the cluster (GeneralInfo.mat mahD)",
    "isi_index": "ISI index of the cluster (GeneralInfo.mat isiIx): fraction of refractory-period violations",
}


def read_clusters(session_path: Path, shank: int) -> tuple:
    """Cluster of each spike (the .clu file's first line is the number of clusters) and its time in samples."""
    session_id = session_path.name
    clusters = np.loadtxt(session_path / f"{session_id}.clu.{shank}", dtype=np.int64, ndmin=1)[1:]
    samples = np.loadtxt(session_path / f"{session_id}.res.{shank}", dtype=np.int64, ndmin=1)
    if len(clusters) != len(samples):
        raise ValueError(f"{session_id} shank {shank}: {len(clusters)} clusters for {len(samples)} spikes")
    return clusters, samples


class PeyracheSortingInterface(BaseDataInterface):
    """Units: the clusters numbered 2 and up of the .clu files, with spike times from the .res files.

    Clusters 0 (artifacts) and 1 (noise and multi-unit activity) are left out. Each unit is matched by shank and
    cluster to the lab's analysis files of the session: the cell list (Analysis/SpikeData.mat), the isolation quality
    (Analysis/GeneralInfo.mat), the head-direction statistics (Analysis/HDCells.mat), and the 2019 buzcode files
    (spikes.cellinfo.mat, CellClass.cellinfo.mat).
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")

    def read_units(self) -> dict:
        """(shank, cluster) -> spike times in samples, sorted, in shank and cluster order."""
        units = {}
        for shank in range(1, len(self.xml_info["spike_groups"]) + 1):
            if not (self.session_path / f"{self.session_id}.clu.{shank}").is_file():
                continue
            clusters, samples = read_clusters(self.session_path, shank)
            for cluster in np.unique(clusters[clusters >= 2]):
                units[(shank, int(cluster))] = np.sort(samples[clusters == cluster])
        return units

    def read_lab_cells(self, units: dict) -> dict:
        """Per-unit values of the lab's analysis files, keyed by (shank, cluster)."""
        analysis = self.session_path / "Analysis"
        values = {key: {} for key in units}
        notes = []

        spike_data_file_path = analysis / "SpikeData.mat"
        cell_list = []
        if spike_data_file_path.is_file():
            spike_data = load_mat(spike_data_file_path)
            cell_list = [
                (int(shank), int(cluster))
                for shank, cluster in zip(np.atleast_1d(spike_data["shank"]), np.atleast_1d(spike_data["cellIx"]))
            ]
            # The lab's spike trains must be the spikes of the same clusters (TSToolbox times in 0.1 ms steps)
            for key, train in zip(cell_list, np.atleast_1d(spike_data["S"].C)):
                times = np.atleast_1d(np.asarray(train.tsd.t, dtype=float)).ravel()
                if key not in units or not np.allclose(
                    np.sort(times), units[key] * TS_PER_SECOND / SAMPLING_RATE, atol=0.51
                ):
                    raise ValueError(f"{self.session_id}: the lab's spike train of {key} is not its cluster")
            for key in cell_list:
                values[key]["in_lab_cell_list"] = True

            # meanWaveF: one (channels, samples) mean waveform per cluster 2 and up, in shank and cluster order
            # (Make_MeanWaveF), of all shanks or of the shanks of the cell list; maxWaveFormIx is the 1-indexed
            # channel within the shank
            if "meanWaveF" in spike_data:
                cell_shanks = sorted({shank for shank, _ in cell_list})
                mean_waveforms = list(np.atleast_1d(spike_data["meanWaveF"]))
                max_indices = np.atleast_1d(spike_data["maxWaveFormIx"]).astype(int)
                waveform_keys = list(units)
                if len(mean_waveforms) != len(waveform_keys):
                    waveform_keys = [key for key in units if key[0] in cell_shanks]
                if len(mean_waveforms) == len(waveform_keys):
                    for key, waveform, max_index in zip(waveform_keys, mean_waveforms, max_indices):
                        values[key]["lab_mean_waveform"] = np.asarray(waveform, dtype=float)
                        values[key]["max_waveform_channel"] = self.xml_info["spike_groups"][key[0] - 1][max_index - 1]
                else:
                    notes.append(
                        f"SpikeData.mat has {len(mean_waveforms)} mean waveforms for {len(waveform_keys)} clusters; "
                        "they were not written"
                    )

        general_info_file_path = analysis / "GeneralInfo.mat"
        if general_info_file_path.is_file() and cell_list:
            general_info = load_mat(general_info_file_path)
            # HDCells_IsolationQuality: one value per cluster 2 and up of the shanks of the cell list, which are the
            # clusters of the cell list itself
            for mat_name, column in (("lratio", "lratio"), ("mahD", "mahalanobis_distance"), ("isiIx", "isi_index")):
                if mat_name not in general_info:
                    continue
                column_values = np.atleast_1d(general_info[mat_name]).astype(float)
                if len(column_values) != len(cell_list):
                    notes.append(
                        f"GeneralInfo.mat {mat_name} has {len(column_values)} values for {len(cell_list)} cells"
                    )
                    continue
                for key, value in zip(cell_list, column_values):
                    values[key][column] = float(value)

        hd_file_path = analysis / "HDCells.mat"
        if hd_file_path.is_file() and cell_list:
            hd_stats = np.atleast_2d(load_mat(hd_file_path, variable_names=["hdCellStats"])["hdCellStats"])
            if hd_stats.shape == (len(cell_list), 5):
                for key, row in zip(cell_list, hd_stats):
                    values[key].update(
                        hd_preferred_direction=float(row[0]),
                        hd_p_value=float(row[1]),
                        hd_kappa=float(row[2]),
                        hd_peak_rate=float(row[3]),
                        is_hd_cell=bool(row[4] == 1),
                    )
            else:
                notes.append(f"HDCells.mat hdCellStats has shape {hd_stats.shape} for {len(cell_list)} cells")

        cellinfo_file_path = self.session_path / f"{self.session_id}.spikes.cellinfo.mat"
        if cellinfo_file_path.is_file():
            cellinfo = load_mat(cellinfo_file_path)["spikes"]
            cellinfo_keys = [
                (int(shank), int(cluster))
                for shank, cluster in zip(np.atleast_1d(cellinfo.shankID), np.atleast_1d(cellinfo.cluID))
            ]
            regions = np.atleast_1d(getattr(cellinfo, "region", np.array([""] * len(cellinfo_keys), dtype=object)))
            raw_waveforms = list(np.atleast_1d(cellinfo.rawWaveform)) if hasattr(cellinfo, "rawWaveform") else []
            max_channels = np.atleast_1d(getattr(cellinfo, "maxWaveformCh", []))
            for index, (key, times, region) in enumerate(zip(cellinfo_keys, np.atleast_1d(cellinfo.times), regions)):
                if key not in units or not np.allclose(
                    np.sort(np.atleast_1d(times)), units[key] / SAMPLING_RATE, atol=0.6 / SAMPLING_RATE
                ):
                    raise ValueError(f"{self.session_id}: the spikes.cellinfo spike train of {key} is not its cluster")
                values[key]["buzcode_region"] = str(region) if isinstance(region, str) else ""
                if len(raw_waveforms) == len(cellinfo_keys):
                    values[key]["buzcode_mean_waveform"] = np.asarray(raw_waveforms[index], dtype=float).ravel()
                if len(max_channels) == len(cellinfo_keys):
                    # maxWaveformCh is the .xml channel number (checked against meanWaveF where both exist)
                    values[key].setdefault("max_waveform_channel", int(max_channels[index]))
                if "lab_mean_waveform" in values[key] and "buzcode_mean_waveform" in values[key]:
                    channels = self.xml_info["spike_groups"][key[0] - 1]
                    row = values[key]["lab_mean_waveform"][channels.index(values[key]["max_waveform_channel"])]
                    # The two are computed from different spike samples, so they match closely but not always
                    # exactly; a correlation this low would mean the units were matched to the wrong waveforms
                    if np.corrcoef(row, values[key]["buzcode_mean_waveform"])[0, 1] < 0.8:
                        raise ValueError(f"{self.session_id}: the two mean waveforms of {key} differ")

            class_file_path = self.session_path / f"{self.session_id}.CellClass.cellinfo.mat"
            if class_file_path.is_file():
                labels = np.atleast_1d(load_mat(class_file_path)["CellClass"].label)
                if len(labels) == len(cellinfo_keys):
                    for key, label in zip(cellinfo_keys, labels):
                        values[key]["cell_type"] = CELL_CLASSES.get(str(label), str(label))
                else:
                    notes.append(f"CellClass.cellinfo.mat has {len(labels)} labels for {len(cellinfo_keys)} cells")
        self.notes = notes
        return values

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        units = self.read_units()
        lab = self.read_lab_cells(units)
        general_info_file_path = self.session_path / "Analysis" / "GeneralInfo.mat"
        regions = {}
        if general_info_file_path.is_file():
            regions = read_shank_structure(load_mat(general_info_file_path, variable_names=["shankStructure"]))

        has = {name for unit_values in lab.values() for name in unit_values}
        description = (
            "Units sorted by the lab with KlustaKwik and Klusters: the clusters numbered 2 and up of the .clu files, "
            "with spike times from the .res files (20 kHz samples). Clusters 0 (artifacts) and 1 (noise and multi-unit "
            "activity) are left out. Every cluster is written, including those on shanks the lab left out of its cell "
            "list; in_lab_cell_list marks the units of the lab's analyses (Analysis/SpikeData.mat)."
        )
        if self.notes:
            description += " Notes: " + "; ".join(self.notes) + "."
        nwbfile.units = Units(name="units", description=description, resolution=1 / SAMPLING_RATE)
        nwbfile.add_unit_column(
            name="shank",
            description=(
                "number of the unit's .clu/.res file (the lab's `shank`, its spike group); the electrode group is the "
                ".xml anatomical group holding the same channels, numbered differently in some sessions"
            ),
        )
        nwbfile.add_unit_column(name="cluster_id", description="cluster number in the .clu file of the shank")
        nwbfile.add_unit_column(
            name="region",
            description=(
                "location of the unit's electrode group (Allen Mouse Brain Atlas names), from the lab's GeneralInfo.mat "
                "shankStructure (thalamus: Anterodorsal nucleus; postsub: Postsubiculum; pfc: Prelimbic area; "
                "hippocampus: Field CA1; rtn: Reticular nucleus of the thalamus); 'unknown' for groups the lab assigned "
                "no region"
            ),
        )
        nwbfile.add_unit_column(
            name="in_lab_cell_list",
            description=(
                "the unit is in the lab's cell list of the session (Analysis/SpikeData.mat), the units of the lab's "
                "analyses; the paper's exact selection of 720 thalamic and 357 post-subicular cells is not recorded"
            ),
        )
        if "buzcode_region" in has:
            nwbfile.add_unit_column(
                name="buzcode_region",
                description=(
                    "region of the unit in the lab's 2019 buzcode spikes.cellinfo.mat (THAL, SUB, or empty); empty for "
                    "units not in that file"
                ),
            )
        if "cell_type" in has:
            nwbfile.add_unit_column(
                name="cell_type",
                description=(
                    "putative cell class of the lab's 2019 buzcode CellClass.cellinfo.mat (pE: putative excitatory, "
                    "pI: putative inhibitory, from waveform and firing features); 'not classified' for units not in "
                    "that file"
                ),
            )
        for name, column_description in QUALITY_COLUMNS.items():
            if name in has:
                nwbfile.add_unit_column(
                    name=name, description=column_description + "; NaN for units not in the cell list"
                )
        if "hd_preferred_direction" in has:
            for name, column_description in HD_COLUMNS.items():
                nwbfile.add_unit_column(name=name, description=column_description)
            nwbfile.add_unit_column(
                name="is_hd_cell",
                description=(
                    "head-direction cell by the lab's criteria (hdCellStats column 5: p < 0.001, kappa > 1 and peak "
                    "rate > 1 Hz); false for units not in the cell list"
                ),
            )
        has_waveforms = "lab_mean_waveform" in has
        if has_waveforms:
            n_channels = max(len(channels) for channels in self.xml_info["spike_groups"])
            n_samples = max(
                values["lab_mean_waveform"].shape[1] for values in lab.values() if "lab_mean_waveform" in values
            )
            nwbfile.add_unit_column(
                name="lab_mean_waveform",
                description=(
                    "mean spike waveform on each channel of the unit's shank, in the order of the shank's channels in "
                    "the .xml file, from the lab's Make_MeanWaveF (Analysis/SpikeData.mat meanWaveF), as (channels, "
                    f"samples at 20 kHz), padded with NaN to {n_channels} channels; in the lab's units, which the files "
                    "do not document (probably ADC steps of the .spk files); NaN for clusters on shanks without "
                    "waveforms"
                ),
            )
        if "buzcode_mean_waveform" in has:
            n_buzcode_samples = max(
                len(values["buzcode_mean_waveform"]) for values in lab.values() if "buzcode_mean_waveform" in values
            )
            nwbfile.add_unit_column(
                name="buzcode_mean_waveform",
                description=(
                    "mean spike waveform on the unit's largest channel (samples at 20 kHz), from the lab's 2019 buzcode "
                    "spikes.cellinfo.mat rawWaveform; in the lab's units, which the files do not document (it equals "
                    "lab_mean_waveform on that channel up to a constant offset, where both exist); NaN for units not "
                    "in that file"
                ),
            )
        if "max_waveform_channel" in has:
            nwbfile.add_unit_column(
                name="max_waveform_channel",
                description=(
                    "channel (.xml numbering) with the largest mean waveform (SpikeData.mat maxWaveFormIx, or "
                    "spikes.cellinfo.mat maxWaveformCh); -1 where neither gives it"
                ),
            )

        channel_ids = list(nwbfile.electrodes["channel_id"][:])
        for (shank, cluster), samples in units.items():
            values = lab[(shank, cluster)]
            anatomical_group = self.xml_info["spike_to_anatomical"][shank - 1]
            region = REGION_LOCATIONS.get(regions.get(anatomical_group), "unknown")
            row = dict(
                spike_times=samples / SAMPLING_RATE,
                electrode_group=nwbfile.electrode_groups[f"group{anatomical_group}"],
                electrodes=[channel_ids.index(channel) for channel in self.xml_info["spike_groups"][shank - 1]],
                shank=shank,
                cluster_id=cluster,
                region=region,
                in_lab_cell_list=values.get("in_lab_cell_list", False),
            )
            if "buzcode_region" in has:
                row["buzcode_region"] = values.get("buzcode_region", "")
            if "cell_type" in has:
                row["cell_type"] = values.get("cell_type", "not classified")
            for name in QUALITY_COLUMNS:
                if name in has:
                    row[name] = values.get(name, np.nan)
            if "hd_preferred_direction" in has:
                for name in HD_COLUMNS:
                    row[name] = values.get(name, np.nan)
                row["is_hd_cell"] = values.get("is_hd_cell", False)
            if has_waveforms:
                waveform = np.full((n_channels, n_samples), np.nan, dtype=np.float32)
                if "lab_mean_waveform" in values:
                    lab_waveform = values["lab_mean_waveform"]
                    waveform[: lab_waveform.shape[0], : lab_waveform.shape[1]] = lab_waveform
                row["lab_mean_waveform"] = waveform
            if "buzcode_mean_waveform" in has:
                waveform = np.full(n_buzcode_samples, np.nan, dtype=np.float32)
                if "buzcode_mean_waveform" in values:
                    waveform[: len(values["buzcode_mean_waveform"])] = values["buzcode_mean_waveform"]
                row["buzcode_mean_waveform"] = waveform
            if "max_waveform_channel" in has:
                row["max_waveform_channel"] = int(values.get("max_waveform_channel", -1))
            nwbfile.add_unit(**row)
            if stub_test and len(nwbfile.units) >= STUB_UNITS:
                return
