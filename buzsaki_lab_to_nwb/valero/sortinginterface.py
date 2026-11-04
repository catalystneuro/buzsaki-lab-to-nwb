"""Units of a Valero session (DANDI:000568)."""

from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.misc import Units

from .valeroutils import electrode_groups, read_session

STUB_UNITS = 5

# Order of the 60 uLED codes in uLEDResponse.cellinfo.mat: codes 1-12 are the 12 uLEDs, and each manipulation group
# adds 100 (codeGroupsLegend)
RESPONSE_GROUPS_DESCRIPTION = (
    "one value per uLED code, in the order of uLEDResponse.code: 1-12, then 101-112, 201-212, 301-312 and 401-412, "
    "where code (c mod 100) is the uLED of the pulses table and the hundreds are the groups of codeGroupsLegend "
    "({legend}); NaN for codes without pulses"
)


class ValeroSortingInterface(BaseDataInterface):
    """Units from spikes.cellinfo.mat, with cell types from cell_metrics.cellinfo.mat and light responses from
    uLEDResponse.cellinfo.mat when those files describe the same units."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.notes = []

    def file(self, suffix: str) -> Path:
        return self.session_path / f"{self.session_id}{suffix}"

    def shanks_from_kilosort(self, spikes: dict) -> Optional[np.ndarray]:
        """Shank of each unit from the Phy/Kilosort folder, for spikes files without shankID (fCamk2, fCamk3 sess13).

        At least 99% of each unit's spikes must be spikes of the Kilosort cluster with the unit's id (the Phy folder
        can hold a later curation), and all the templates of that cluster must peak on one shank (channel_shanks.npy).
        """
        clustering = spikes.get("processinginfo", {}).get("params", {}).get("clusteringpath")
        if not isinstance(clustering, str):
            return None
        folder = self.session_path / clustering
        names = ["spike_clusters", "spike_templates", "spike_times", "templates", "channel_shanks", "channel_map"]
        if not all((folder / f"{name}.npy").is_file() for name in names):
            return None
        spike_clusters, spike_templates, spike_times = (
            np.load(folder / f"{name}.npy").ravel() for name in ("spike_clusters", "spike_templates", "spike_times")
        )
        channel_map = np.load(folder / "channel_map.npy").ravel()
        channel_shanks = np.load(folder / "channel_shanks.npy").ravel()
        peak_channels = channel_map[np.abs(np.load(folder / "templates.npy")).max(axis=1).argmax(axis=1)]
        shank_of_channel = dict(zip(channel_map.tolist(), channel_shanks.tolist()))
        shanks, n_exact, lowest_overlap = [], 0, 1.0
        for cluster, samples in zip(spikes["cluID"], spikes["ts"]):
            in_cluster = spike_clusters == cluster
            cluster_samples = np.sort(spike_times[in_cluster].astype(np.int64))
            samples = np.sort(np.asarray(samples, dtype=np.int64))
            overlap = float(np.isin(samples, cluster_samples).mean()) if samples.size else 0.0
            if overlap < 0.99:
                return None
            n_exact += int(np.array_equal(cluster_samples, samples))
            lowest_overlap = min(lowest_overlap, overlap)
            unit_shanks = {shank_of_channel[peak_channels[t]] for t in np.unique(spike_templates[in_cluster])}
            if len(unit_shanks) != 1:
                return None
            shanks.append(int(unit_shanks.pop()))
        if n_exact == len(shanks):
            check = "after checking that each cluster's spikes are the unit's spikes"
        else:
            check = (
                f"the clusters' spikes equal the unit's spikes for {n_exact} of {len(shanks)} units; for the others, "
                + (
                    "all the unit's spikes are in the cluster, which has more spikes"
                    if lowest_overlap == 1.0
                    else f"at least {np.floor(lowest_overlap * 1e4) / 100:.2f}% of the unit's spikes are in the cluster"
                )
            )
        self.notes.append(
            f"spikes.cellinfo.mat has no shankID; the shank of each unit was taken from the lab's {clustering} "
            f"Phy folder (the shank of the peak channel of the cluster's Kilosort templates; {check})"
        )
        return np.asarray(shanks)

    def read_cell_metrics(self, spikes: dict) -> Optional[dict]:
        """cell_metrics, if its units are the units of spikes.cellinfo.mat (same cluster ids, in the same order)."""
        if not self.file(".cell_metrics.cellinfo.mat").is_file():
            self.notes.append("the session has no cell_metrics.cellinfo.mat, so the units have no cell type")
            return None
        cell_metrics = read_mat(
            str(self.file(".cell_metrics.cellinfo.mat")),
            variable_names=["cell_metrics"],
        )["cell_metrics"]
        if not np.array_equal(np.asarray(cell_metrics["cluID"]), np.asarray(spikes["cluID"])):
            self.notes.append(
                f"cell_metrics.cellinfo.mat and uLEDResponse.cellinfo.mat describe {len(cell_metrics['cluID'])} "
                f"units of a different spike sorting (cluster ids {int(np.min(cell_metrics['cluID']))}-"
                f"{int(np.max(cell_metrics['cluID']))}) than the {len(spikes['cluID'])} units of spikes.cellinfo.mat "
                "written here, so cell types and light responses are not given"
            )
            return None
        return cell_metrics

    def read_light_responses(self, n_units: int) -> Optional[dict]:
        if not self.file(".uLEDResponse.cellinfo.mat").is_file():
            return None
        content = read_mat(str(self.file(".uLEDResponse.cellinfo.mat")))
        # Two versions of the lab's file: spikesResponses (60 codes, 5 manipulation groups) and uLEDResponses (12 codes)
        responses = content.get("spikesResponses", content.get("uLEDResponses"))
        if responses is None:
            return None
        if np.shape(responses["rateDuringPulse"])[0] != n_units:
            return None

        def flags(name):
            # MATLAB grows a logical array only up to its last true element, so missing trailing entries are false
            values = np.zeros(n_units, dtype=bool)
            source = np.atleast_1d(np.asarray(responses[name], dtype=bool))
            values[: len(source)] = source
            if len(source) < n_units:
                self.notes.append(
                    f"uLEDResponse.{name} has {len(source)} entries for {n_units} units; the missing trailing "
                    "entries are taken as false"
                )
            return values

        return dict(
            light_driven=flags("drivenCells"),
            light_inhibited=flags("inhibitedCells"),
            on_non_stimulated_shank=flags("unisInNonStimulatedShanks"),
            rate_during_pulse=np.asarray(responses["rateDuringPulse"], dtype=float),
            rate_before_pulse=np.asarray(responses["rateBeforePulse"], dtype=float),
            response_test=np.asarray(responses["bootsTrapTest"], dtype=float),
            codes_text=(
                RESPONSE_GROUPS_DESCRIPTION.format(
                    legend=", ".join(str(item) for item in responses["codeGroupsLegend"])
                )
                if "codeGroupsLegend" in responses
                else "one value per uLED code 1-12 of the pulses table (uLEDResponses.codes); NaN for uLEDs without "
                "pulses"
            ),
        )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.notes = []
        spikes = read_mat(str(self.file(".spikes.cellinfo.mat")))["spikes"]
        session = read_session(self.session_path)
        sampling_rate = float(session["extracellular"]["sr"])
        shank_channels = electrode_groups(session)
        n_units = len(spikes["cluID"])

        if "shankID" in spikes:
            shanks = np.asarray(spikes["shankID"], dtype=int)
        else:
            shanks = self.shanks_from_kilosort(spikes)
            if shanks is None:
                self.notes.append("spikes.cellinfo.mat has no shankID, and the shanks could not be recovered")
        cell_metrics = self.read_cell_metrics(spikes)
        light = self.read_light_responses(n_units) if cell_metrics is not None else None
        has_waveforms = "filtWaveform" in spikes
        if not has_waveforms:
            self.notes.append("spikes.cellinfo.mat has no waveforms")

        description = (
            "units sorted with Kilosort and curated in Phy by the lab, from spikes.cellinfo.mat"
            + (
                "; waveform_mean is the lab's mean filtered waveform (filtWaveform: 500-8000 Hz, from the .dat file) "
                "on the unit's peak channel, converted from uV to volts"
                if has_waveforms
                else ""
            )
            + "".join(f"; {note}" for note in self.notes)
        )
        nwbfile.units = Units(
            name="units",
            description=description,
            resolution=1 / sampling_rate,
            waveform_rate=sampling_rate if has_waveforms else None,
            waveform_unit="volts",
        )
        nwbfile.add_unit_column(name="cluster_id", description="Phy cluster id (spikes.cluID)")
        nwbfile.add_unit_column(name="unit_id", description="the lab's unit number in the session (spikes.UID)")
        if shanks is not None:
            nwbfile.add_unit_column(name="shank", description="1-indexed shank of the unit")
        if "maxWaveformCh" in spikes:
            nwbfile.add_unit_column(
                name="max_waveform_channel", description="0-indexed channel with the largest waveform (maxWaveformCh)"
            )
        if cell_metrics is not None:
            nwbfile.add_unit_column(
                name="cell_type",
                description="putative cell type from CellExplorer (cell_metrics.putativeCellType): Pyramidal Cell, "
                "Narrow Interneuron or Wide Interneuron",
            )
            nwbfile.add_unit_column(
                name="deep_superficial",
                description="position in the CA1 pyramidal layer from the ripple polarity "
                "(cell_metrics.deepSuperficial)",
            )
        if light is not None:
            nwbfile.add_unit_column(
                name="light_driven", description="the unit was driven by at least one uLED (uLEDResponse.drivenCells)"
            )
            nwbfile.add_unit_column(
                name="light_inhibited",
                description="the unit was inhibited by at least one uLED (uLEDResponse.inhibitedCells)",
            )
            nwbfile.add_unit_column(
                name="on_non_stimulated_shank",
                description="the unit is on the control shank, which had no stimulating uLEDs "
                "(uLEDResponse.unisInNonStimulatedShanks)",
            )
            codes = light["codes_text"]
            nwbfile.add_unit_column(
                name="light_rate_during_pulse",
                description=f"firing rate (Hz) during the pulses of each uLED (uLEDResponse.rateDuringPulse); {codes}",
            )
            nwbfile.add_unit_column(
                name="light_rate_before_pulse",
                description=f"firing rate (Hz) before the pulses of each uLED (uLEDResponse.rateBeforePulse); {codes}",
            )
            nwbfile.add_unit_column(
                name="light_response_test",
                description="result of the lab's bootstrap test of the response to each uLED "
                f"(uLEDResponse.bootsTrapTest): 1 driven, -1 inhibited, 0 no response; {codes}",
            )

        units = range(min(n_units, STUB_UNITS) if stub_test else n_units)
        for index in units:
            row = dict(
                spike_times=np.asarray(spikes["times"][index], dtype=float),
                cluster_id=int(spikes["cluID"][index]),
                unit_id=int(spikes["UID"][index]),
            )
            if shanks is not None:
                shank = int(shanks[index])
                row.update(
                    shank=shank,
                    electrode_group=nwbfile.electrode_groups[f"shank{shank}"],
                    electrodes=[int(channel) for channel in shank_channels[shank - 1]],
                )
            if "maxWaveformCh" in spikes:
                row["max_waveform_channel"] = int(spikes["maxWaveformCh"][index])
            if has_waveforms:
                row["waveform_mean"] = np.asarray(spikes["filtWaveform"][index], dtype=float) * 1e-6
            if cell_metrics is not None:
                row.update(
                    cell_type=str(cell_metrics["putativeCellType"][index]),
                    deep_superficial=str(cell_metrics["deepSuperficial"][index]),
                )
            if light is not None:
                row.update(
                    light_driven=bool(light["light_driven"][index]),
                    light_inhibited=bool(light["light_inhibited"][index]),
                    on_non_stimulated_shank=bool(light["on_non_stimulated_shank"][index]),
                    light_rate_during_pulse=light["rate_during_pulse"][index],
                    light_rate_before_pulse=light["rate_before_pulse"][index],
                    light_response_test=light["response_test"][index],
                )
            nwbfile.add_unit(**row)
