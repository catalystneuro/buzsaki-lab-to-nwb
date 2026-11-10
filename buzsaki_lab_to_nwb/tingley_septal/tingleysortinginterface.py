"""Units of a Tingley session (DANDI:000213, DANDI:000218)."""

from collections import Counter
from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.misc import Units

from .tingleyutils import read_clu_res, read_mat, read_session_info, read_session_xml

STUB_UNITS = 5


class TingleySortingInterface(BaseDataInterface):
    """Units from the lab's <session>.spikes.cellinfo.mat (buzcode), or from its .clu.N/.res.N files when the session
    has no cellinfo file, with the isolation metrics of <session>.isolationMetrics.cellinfo.mat where it exists.

    Where both exist, the cellinfo units are the clusters 2 and up of the .clu/.res files (checked on DT2 0304, DT8 0207
    and DT9 0525: same spikes).
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name
        self.xml_info = read_session_xml(self.session_path / f"{self.session_id}.xml")
        self.cellinfo_file_path = self.session_path / f"{self.session_id}.spikes.cellinfo.mat"

    def has_units(self) -> bool:
        return self.cellinfo_file_path.is_file() or (self.session_path / f"{self.session_id}.clu.1").is_file()

    def read_units(self) -> tuple:
        """A list of unit dicts and the name of the source."""
        sampling_rate = self.xml_info["sampling_rate"]
        if self.cellinfo_file_path.is_file():
            spikes = read_mat(self.cellinfo_file_path)["spikes"]
            n_units = len(spikes["times"])
            regions = spikes.get("region") or [""] * n_units
            units = [
                dict(
                    unit_id=int(np.ravel(spikes["UID"])[index]),
                    spike_times=np.asarray(spikes["times"][index], dtype=float).ravel(),
                    shank=int(np.ravel(spikes["shankID"])[index]),
                    cluster=int(np.ravel(spikes["cluID"])[index]),
                    region=str(regions[index]),
                    max_waveform_channel=int(np.ravel(spikes["maxWaveformCh"])[index]),
                    raw_waveform=np.asarray(spikes["rawWaveform"][index], dtype=float).ravel(),
                )
                for index in range(n_units)
            ]
            return units, self.cellinfo_file_path.name
        session_info = read_session_info(self.session_path, self.session_id)
        channel_regions = session_info["region"] if session_info and session_info["region"] else None
        units = []
        for index, ((shank, cluster), samples) in enumerate(
            read_clu_res(self.session_path, self.session_id, len(self.xml_info["shank_channels"])).items()
        ):
            region = ""
            if channel_regions is not None:
                labels = Counter(channel_regions[channel] for channel in self.xml_info["shank_channels"][shank - 1])
                region = labels.most_common(1)[0][0] if len(labels) == 1 else ""
            units.append(
                dict(
                    unit_id=index + 1,
                    spike_times=samples / sampling_rate,
                    shank=shank,
                    cluster=cluster,
                    region=region,
                    max_waveform_channel=-1,
                    raw_waveform=None,
                )
            )
        return units, f"{self.session_id}.clu.N and .res.N"

    def read_isolation_metrics(self, unit_ids: list):
        file_path = self.session_path / f"{self.session_id}.isolationMetrics.cellinfo.mat"
        if not file_path.is_file():
            return None
        metrics = read_mat(file_path)["isolationMetrics"]
        ids = [int(unit_id) for unit_id in np.ravel(metrics["UID"])]
        if not set(unit_ids) <= set(ids):
            # Computed for another sorting of the session: the metrics cannot be matched to these units
            self.isolation_note = (
                f" {file_path.name} lists other units than the spikes.cellinfo file (it was computed for another "
                "sorting of the session), so no isolation metrics are given."
            )
            return None
        rows = {unit_id: index for index, unit_id in enumerate(ids)}
        return dict(
            isolation_distance=[float(np.ravel(metrics["isoDist_fet"])[rows[unit_id]]) for unit_id in unit_ids],
            l_ratio=[float(np.ravel(metrics["lratio_fet"])[rows[unit_id]]) for unit_id in unit_ids],
            waveform_amplitude=[float(np.ravel(metrics["waveformAmplitude"])[rows[unit_id]]) for unit_id in unit_ids],
            amplitude_unit=str(metrics.get("waveformUnits", "")),
        )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        if not self.has_units():
            return
        units, source = self.read_units()
        if stub_test:
            units = units[:STUB_UNITS]
        if not units:
            return
        sampling_rate = self.xml_info["sampling_rate"]
        unsorted = [unit["unit_id"] for unit in units if np.any(np.diff(unit["spike_times"]) < 0)]
        from_cellinfo = source.endswith("cellinfo.mat")
        self.isolation_note = ""
        metrics = self.read_isolation_metrics([unit["unit_id"] for unit in units]) if from_cellinfo else None

        description = (
            f"Units of {source}: spikes detected with SpikeDetekt and clustered with KlustaKwik, then curated by hand "
            "in KlustaViewa by the lab (clusters 2 and up of the .clu files). Spike times are seconds from the start "
            "of the recording (sample / 20 kHz)."
        )
        if unsorted:
            description += (
                f" The spike times of {len(unsorted)} unit(s) (ids {', '.join(map(str, unsorted))}) are not in "
                "increasing order in the source; they are sorted here."
            )
        if not from_cellinfo:
            description += (
                " The session has no spikes.cellinfo.mat, so units are numbered 1 to n in spike-group and cluster "
                "order, their region is the region of their spike group's channels in sessionInfo.region, and no "
                "waveforms are written (the lab's .spk files are not on the share)."
            )
        nwbfile.units = Units(name="units", description=description + self.isolation_note, resolution=1 / sampling_rate)
        nwbfile.add_unit_column(name="unit_name", description="the lab's unit ID (spikes.cellinfo UID)")
        nwbfile.add_unit_column(name="shank", description="1-based spike group (shank) of the unit")
        nwbfile.add_unit_column(name="cluster", description="cluster number in the .clu file of the spike group")
        nwbfile.add_unit_column(
            name="region",
            description=(
                "the lab's region label of the unit (spikes.cellinfo region, or the spike group's sessionInfo.region "
                "label for sessions without a cellinfo file): ls (lateral septum), hpc (the probe aimed at dorsal CA1, "
                "not resolved to a subfield), ca1, ca3, and the structures the probes passed through on their way "
                "down (ppc, acg, cc, ms, sFi); empty if not known"
            ),
        )
        if from_cellinfo:
            nwbfile.add_unit_column(
                name="max_waveform_channel",
                description="0-based channel with the largest waveform (spikes.cellinfo maxWaveformCh)",
            )
            nwbfile.add_unit_column(
                name="raw_waveform",
                description=(
                    "mean wide-band waveform of the unit on its max_waveform_channel, 32 samples at 20 kHz (1.6 ms; "
                    "spikes.cellinfo rawWaveform), in the lab's units, which the source does not state"
                ),
            )
        if metrics is not None:
            nwbfile.add_unit_column(
                name="isolation_distance",
                description="isolation distance of the cluster in feature space (isolationMetrics isoDist_fet)",
            )
            nwbfile.add_unit_column(
                name="l_ratio",
                description="L-ratio of the cluster in feature space, as computed by the lab (isolationMetrics lratio_fet)",
            )
            nwbfile.add_unit_column(
                name="waveform_amplitude",
                description=f"waveform amplitude, in {metrics['amplitude_unit'] or 'unstated units'} "
                "(isolationMetrics waveformAmplitude)",
            )

        channel_ids = list(nwbfile.electrodes["channel_id"][:])
        for index, unit in enumerate(units):
            shank = unit["shank"]
            values = dict(unit_name=str(unit["unit_id"]), shank=shank, cluster=unit["cluster"], region=unit["region"])
            if from_cellinfo:
                values.update(max_waveform_channel=unit["max_waveform_channel"], raw_waveform=unit["raw_waveform"])
            if metrics is not None:
                values.update(
                    isolation_distance=metrics["isolation_distance"][index],
                    l_ratio=metrics["l_ratio"][index],
                    waveform_amplitude=metrics["waveform_amplitude"][index],
                )
            nwbfile.add_unit(
                id=unit["unit_id"],
                spike_times=np.sort(unit["spike_times"]),
                electrode_group=nwbfile.electrode_groups[f"group{shank}"],
                electrodes=[channel_ids.index(channel) for channel in self.xml_info["shank_channels"][shank - 1]],
                **values,
            )
