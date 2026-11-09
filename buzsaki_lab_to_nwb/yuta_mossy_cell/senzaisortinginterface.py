"""Units of a Senzai session (DANDI:000003)."""

from pathlib import Path
from typing import Optional, Union

import h5py
import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile
from pynwb.misc import Units

from .senzaiutils import open_published, FINE_CELL_TYPES, REGIONS, read_session_xml, read_unit_summary

# .spk spikes whose samples are all 0 or reach beyond 20,000 steps (7.6 mV) are damaged blocks of the lab's file
DAMAGED_STEPS = 20_000
STUB_UNITS = 5

QUALITY_DESCRIPTION = (
    "{name} from the lab's unit summary (DG_all_6__UnitFeatureSummary_add.mat); -1 for units not in the summary"
)


class SenzaiSortingInterface(BaseDataInterface):
    """Units: the clusters numbered 2 and up in the .clu.N files, with spike times from the .res.N files.

    Their cell type, region, quality and optogenetic tagging come from the row of the lab's unit summary with the same
    session, shank and cluster. Their waveforms come from the session's earlier DANDI file, whose spike times are the
    same spikes in the same order (checked), because most .spk files are not on the public share.
    """

    def __init__(
        self,
        folder_path: DirectoryPath,
        unit_summary_file_path: FilePath,
        published_nwb_file_path: Optional[Union[FilePath, str]] = None,  # a path, or a URL to stream
        verbose: bool = False,
    ):
        super().__init__(
            folder_path=folder_path,
            unit_summary_file_path=unit_summary_file_path,
            published_nwb_file_path=published_nwb_file_path,
            verbose=verbose,
        )
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")

    def read_units(self) -> dict:
        """Map (shank, cluster) to spike times in samples, in shank and cluster order."""
        units = {}
        for shank_index, _ in enumerate(self.xml_info["shank_channels"]):
            shank = shank_index + 1
            clu_file_path = self.session_path / f"{self.session_id}.clu.{shank}"
            if not clu_file_path.is_file():
                continue
            clusters = np.loadtxt(clu_file_path, dtype=np.int64, ndmin=1)[
                1:
            ]  # the first line is the number of clusters
            if not np.any(clusters > 1):
                continue  # only artifact and noise clusters (YutaMouse33-150223 shank 8, whose .res is not on the share)
            samples = np.loadtxt(self.session_path / f"{self.session_id}.res.{shank}", dtype=np.int64, ndmin=1)
            for cluster in np.unique(clusters[clusters > 1]):
                units[(shank, int(cluster))] = samples[clusters == cluster]
        return self.replace_resorted_shanks(units)

    def replace_resorted_shanks(self, units: dict) -> dict:
        """Take a shank's units from the earlier DANDI file when the lab's share holds a later sorting of it.

        The earlier file holds each shank's clusters 2 and up in cluster order (its shank_id is the cluster number
        minus 2). Where a shank's spikes there differ from those of the .clu/.res files on the share, the share's files
        are a later re-sorting (the session folder keeps dated earlier .clu files), and the earlier file's units of
        that shank are used, so that the units are those the lab's unit summary and the earlier file describe.
        """
        self.shanks_from_published_file = []
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is None:
            return units
        sampling_rate = self.xml_info["sampling_rate"]
        with open_published(published_nwb_file_path) as file:
            published = file["units"]
            if "waveforms" not in published or "electrode_group" not in published or "shank_id" not in published:
                return units  # an earlier file without waveforms or shanks gives nothing to compare or take
            groups = [file[reference].name.rsplit("/", 1)[-1] for reference in published["electrode_group"][:]]
            ends = published["spike_times_index"][:]
            starts = np.concatenate([[0], ends[:-1]])
            spike_times = published["spike_times"][:]
            if np.array_equal(
                np.rint(spike_times * sampling_rate).astype(np.int64), np.concatenate(list(units.values()))
            ):
                return units  # every shank's sorting is the earlier file's
            shank_ids = published["shank_id"][:]
        replaced = {}
        for shank in sorted(
            {key[0] for key in units} | {int(g.removeprefix("shank")) for g in groups if g.startswith("shank")}
        ):
            # Units without spikes in the earlier file (it keeps some) are not clusters of the .clu files
            rows = [row for row, group in enumerate(groups) if group == f"shank{shank}" and ends[row] > starts[row]]
            published_units = {
                (shank, int(shank_ids[row]) + 2): np.rint(spike_times[starts[row] : ends[row]] * sampling_rate).astype(
                    np.int64
                )
                for row in rows
            }
            ours = {key: value for key, value in units.items() if key[0] == shank}
            same = list(ours) == list(published_units) and all(
                np.array_equal(ours[key], published_units[key]) for key in ours
            )
            if not same and rows:
                self.shanks_from_published_file.append(shank)
            replaced.update(ours if same or not rows else published_units)
        return replaced

    def read_published_waveforms(self, units: dict):
        """Per-unit waveforms from the earlier DANDI file, after checking that its spikes are these spikes."""
        published_nwb_file_path = self.source_data["published_nwb_file_path"]
        if published_nwb_file_path is None:
            return None
        self._published_file = open_published(published_nwb_file_path)
        published = self._published_file["units"]
        if "waveforms" not in published:
            return None
        sampling_rate = self.xml_info["sampling_rate"]
        published_samples = np.rint(published["spike_times"][:] * sampling_rate).astype(np.int64)
        samples = np.concatenate(list(units.values()))
        if not np.array_equal(published_samples, samples):
            raise ValueError(
                f"The spikes of the earlier DANDI file of {self.session_id} are not the spikes of its .res/.clu files "
                "in shank and cluster order, so its waveforms cannot be assigned to units"
            )
        row_ends = published["waveforms_index"][:]
        row_starts = np.concatenate([[0], row_ends[:-1]])
        waveforms = {}
        first_spike = 0
        for key, unit_samples in units.items():
            last_spike = first_spike + len(unit_samples)
            n_channels = int(row_ends[first_spike] - row_starts[first_spike])
            rows = published["waveforms"][row_starts[first_spike] : row_ends[last_spike - 1]]
            # The earlier files hold the .spk values in volts as if each step were a microvolt
            waveforms[key] = np.rint(rows.reshape(len(unit_samples), n_channels, -1) * 1e6).astype(np.int16)
            first_spike = last_spike
        return waveforms

    @staticmethod
    def sort_spikes(units: dict, waveforms: Optional[dict]) -> tuple:
        """Each unit's spikes in time order, with their waveforms, and without exact repeats.

        The units the earlier DANDI file gives for a re-sorted shank keep its spike order; unit 1 of
        YutaMouse33-150223 there is two time-ordered runs of spikes one after the other (327,680 spikes from 17,225 s,
        then 490,362 from 0.3 s), 2,328 of whose times are in both. Returns the units, the waveforms and a note for the
        units table naming the units changed.
        """
        changed = []
        for key, samples in list(units.items()):
            order = np.argsort(samples, kind="stable")
            sorted_samples = samples[order]
            keep = np.concatenate([[True], np.diff(sorted_samples) != 0])
            if np.array_equal(order, np.arange(len(samples))) and keep.all():
                continue
            units[key] = sorted_samples[keep]
            if waveforms is not None and key in waveforms:
                waveforms[key] = np.asarray(waveforms[key])[order][keep]
            changed.append(f"shank {key[0]} cluster {key[1]} ({int((~keep).sum())} repeated spike times dropped)")
        note = (
            ". The spike times of " + "; ".join(changed) + " were not in time order in the earlier file and are "
            "sorted here, with their waveforms; a spike time listed twice is kept once"
            if changed
            else ""
        )
        return units, waveforms, note

    def read_spk_waveforms(self, units: dict):
        """Per-unit waveforms in steps from the .spk files, when every shank with units has one."""
        n_samples = self.xml_info["spikes_n_samples"]
        waveforms = {}
        for shank in sorted({shank for shank, _ in units}):
            spk_file_path = self.session_path / f"{self.session_id}.spk.{shank}"
            if not spk_file_path.is_file():
                return None
            clusters = np.loadtxt(self.session_path / f"{self.session_id}.clu.{shank}", dtype=np.int64, ndmin=1)[1:]
            n_channels = len(self.xml_info["shank_channels"][shank - 1])
            spikes = np.memmap(spk_file_path, dtype=np.int16, mode="r").reshape(len(clusters), n_samples, n_channels)
            for unit_shank, cluster in units:
                if unit_shank == shank:
                    # .spk files are (spikes, samples, channels)
                    waveforms[(shank, cluster)] = np.asarray(spikes[clusters == cluster]).transpose(0, 2, 1)
        return waveforms

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        units = self.read_units()
        waveforms = self.read_published_waveforms(units)
        if waveforms is None:
            waveforms = self.read_spk_waveforms(units)
        if stub_test:
            units = dict(list(units.items())[:STUB_UNITS])
        units, waveforms, unsorted_note = self.sort_spikes(units, waveforms)

        summary = read_unit_summary(Path(self.source_data["unit_summary_file_path"]))
        summary = summary[summary.fname == self.session_id].set_index(["shank", "unitIDshank"])
        sampling_rate = self.xml_info["sampling_rate"]

        nwbfile.units = Units(
            name="units",
            description=(
                "units sorted with KlustaKwik and curated in Klusters (clusters 2 and up of the .clu files); spike "
                "waveforms are 32 samples (1.6 ms at 20 kHz) on each channel of the unit's shank, as stored in the "
                "lab's .spk files, as the lab's int16 steps (multiply by 0.3815 uV, the Amplipex system's 10 V over 16 "
                "bits at x400, for volts); some spikes' stored waveforms are damaged (every sample 0, or a sample beyond "
                "20,000 steps, 7.6 mV) and are kept as stored, counted in damaged_waveforms"
                + (
                    ". The .clu/.res files of shank(s) "
                    + ", ".join(map(str, self.shanks_from_published_file))
                    + " on the lab's share are a later re-sorting that differs from the units of the lab's unit summary "
                    "and of the earlier DANDI file (DANDI:000003 version 0.260218.2052), so those shanks' units, spike "
                    "times and waveforms are taken from the earlier file"
                    if self.shanks_from_published_file
                    else ""
                )
                + unsorted_note
            ),
            resolution=1 / sampling_rate,
            waveform_rate=sampling_rate,
            waveform_unit="int16 steps of 0.3815 uV",
        )
        nwbfile.add_unit_column(name="shank", description="1-indexed shank the unit was detected on")
        nwbfile.add_unit_column(
            name="damaged_waveforms",
            description=(
                "number of the unit's spikes whose stored waveform is damaged (every sample 0, or a sample beyond "
                "20,000 steps); their waveforms are kept as stored"
            ),
        )
        nwbfile.add_unit_column(name="cluster_id", description="cluster number in the .clu file of the shank")
        nwbfile.add_unit_column(
            name="global_id", description="unitID of the lab's unit summary; -1 for units not in the summary"
        )
        nwbfile.add_unit_column(
            name="cell_type",
            description=(
                "cell type from the lab's unit summary (fineCellType); excitatory cells are granule cells in the "
                "dentate gyrus and pyramidal cells in CA3; 'not in unit summary' for units the authors did not include"
            ),
        )
        nwbfile.add_unit_column(
            name="region", description="region of the unit in the lab's unit summary (DG or CA3); 'unknown' if absent"
        )
        for name in ("ACGquality", "UnitStability"):
            nwbfile.add_unit_column(name=name, description=QUALITY_DESCRIPTION.format(name=name))
        for name, cell in (("sstcell", "SST"), ("drd2cellGOOD", "DRD2"), ("pomccell", "POMC")):
            extra = (
                "; the summary's drd2cell is 0 for every unit, and drd2cellGOOD marks the 42 units whose firing green "
                "light suppressed, 29 of them mossy cells, as in the paper"
                if cell == "DRD2"
                else ""
            )
            nwbfile.add_unit_column(
                name=f"{cell.lower()}_tagged",
                description=(
                    f"the unit responded to light as a {cell}-expressing cell ({name} of the lab's unit summary{extra})"
                ),
            )

        for (shank, cluster), unit_samples in units.items():
            group = nwbfile.electrode_groups[f"shank{shank}"]
            # In the order of the shank's channels in the .xml file, which is the channel order of the waveforms
            channel_ids = list(nwbfile.electrodes["channel_id"][:])
            electrodes = [channel_ids.index(channel) for channel in self.xml_info["shank_channels"][shank - 1]]
            if (shank, cluster) in summary.index:
                row = summary.loc[(shank, cluster)]
                region = REGIONS.get(int(row.region), "unknown")
                if int(row.fineCellType) == 1:
                    cell_type = {"DG": "granule cell", "CA3": "CA3 pyramidal cell"}.get(region, "excitatory cell")
                else:
                    cell_type = FINE_CELL_TYPES[int(row.fineCellType)]
                values = dict(
                    global_id=int(row.unitID),
                    ACGquality=int(row.ACGquality),
                    UnitStability=int(row.UnitStability),
                    sst_tagged=bool(row.sstcell),
                    drd2_tagged=bool(row.drd2cellGOOD),
                    pomc_tagged=bool(row.pomccell),
                )
            else:
                region, cell_type = "unknown", "not in unit summary"
                values = dict(
                    global_id=-1,
                    ACGquality=-1,
                    UnitStability=-1,
                    sst_tagged=False,
                    drd2_tagged=False,
                    pomc_tagged=False,
                )
            unit_waveforms, n_damaged = None, 0
            if waveforms is not None:
                steps = waveforms[(shank, cluster)]
                unit_waveforms = np.asarray(steps, dtype=np.int16)
                damaged = (steps == 0).all(axis=(1, 2)) | (np.abs(steps.astype(np.int32)) > DAMAGED_STEPS).any(
                    axis=(1, 2)
                )
                n_damaged = int(damaged.sum())
            nwbfile.add_unit(
                spike_times=unit_samples / sampling_rate,
                electrode_group=group,
                electrodes=electrodes,
                shank=shank,
                cluster_id=cluster,
                cell_type=cell_type,
                region=region,
                waveforms=unit_waveforms,
                damaged_waveforms=n_damaged,
                **values,
            )
