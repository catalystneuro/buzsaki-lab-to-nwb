# Petersen and Buzsaki 2020 (DANDI:000059)

Conversion with NeuroConv; the earlier nwb-conversion-tools converter and its 2023 fix scripts were replaced (the
scripts are kept in `8_15_2023_dandiset_fixes/` for the record). The fixes follow the triage in
https://github.com/catalystneuro/buzsaki-lab-to-nwb/issues/78.

```
python -m buzsaki_lab_to_nwb.petersen.convert_session PetersenP/MS21/Peter_MS21_180719_155941_concat out.nwb \
    --published-raw <the session's desc-raw file of DANDI:000059> [--no-wideband] [--stub]
```

## Sources (Buzsaki lab Globus share, `PetersenP/<rat>/<session>/`)

- `<session>.xml`: channels and electrode (spike) groups.
- `<session>.session.mat` (CellExplorer session metadata): probes, `brainRegions` (CA1, 1-based channels),
  `channelTags` (Theta, Ripple, Bad), `epochs`, `extracellular.leastSignificantBit`.
- `Kilosort_*/`: Phy output (`spike_times.npy`, `spike_clusters.npy`, `amplitudes.npy`, `params.py`) and labels in
  `cluster_info.tsv`, `cluster_group.tsv` or the older `cluster_groups.csv` (MS10).
- `<session>.cell_metrics.cellinfo.mat` (CellExplorer): one entry per curated cell, linked to Phy by `cluID`.
- `<session>.animal.behavior.mat` and `<session>.trials.behavior.mat`, else `animal.mat` and `trials.mat`: the first
  pair whose trial sample indices fall within the tracking is used (in MS21-180712 `animal.mat` is a stale segment).
- `temperature.mat`: the measured septal temperature (20 Hz).
- `<session>.cooling.manipulation.mat`: cooling onset/offset and the `cooling` and `nocooling` intervals.
- `<session>.SleepState.states.mat`: SleepScoreMaster states, where present.
- LFP and wide-band signal: the lab's `.lfp`/`.dat` files are not on the share for most sessions, so they are copied
  from the session's `desc-raw` file of DANDI:000059 (0.250624.0444). Its columns are the .dat channels 0 to n-1 (the
  largest spike of each CellExplorer cell is on its `maxWaveformCh`), but its electrodes table put rows 0-9 in shank1,
  10-19 in shank2 and so on; the new electrodes table takes the groups from the .xml.

## Decisions

- Units: every Phy cluster, with `quality` from the Phy labels; the curated cells (the paper's cells) are the 'good'
  units, which are exactly the CellExplorer cells (checked), with `cell_type`, `region`, `cell_metrics_id` and
  `max_waveform_channel`. Spike times are rebuilt from the Phy files per cluster and sorted, which also fixes the
  wrapped spike-times index of the earlier MS22-180719 file. Clusters absent from the label file are 'unsorted' (Phy's
  default). `pc_features` of the earlier files is not written (uninterpretable without `pc_feature_ind`).
- Temperature: `MeasuredTemperature` from `temperature.mat` where it exists; `animal.temperature` is then left out (it
  is either a copy of the measurement or a model that the measurement contradicts). Without a measurement (MS10) the
  curve is written as `ModelledTemperature`, described as not a measurement.
- Trials: times are `animal.time[start - 1]` and `animal.time[end - 1]` (the lab's indices are 1-based: the
  per-sample trial vector `trials2` starts at `start - 1`); the earlier files were one sample late. `condition` is the
  lab's `stat` label (Left/Right); error trials are exactly the trials where the tracked rat ran to the other side arm,
  so `condition` is the side arm of the trial, not always the side run. `cooling_state` names the lab's codes by
  `animal.state_labels` (1 Pre, 2 Cooling, 3 Post); code 0 is 'transition (excluded)', the trials the lab left out of
  every state (the earlier files called it "Cooling off"). When there are fewer codes than trials (MS21-180627) the
  codes are kept for the first trials if they match the per-sample state vector, and the rest are 'not labelled'.
  `temperature` is added where `trials.temperature` exists.
- `LinearizedPosition` is written (the earlier converter's field test always failed). Acceleration has unit "unknown":
  in some sessions it is the per-sample change of speed.
- Intervals: `cooling` (nocooling, cooling and the transition gaps between them) and `epochs` from session.mat. The
  2018-07-19 sessions (MS21, MS22) keep the lab's cooling labels; their descriptions note that the measured
  temperature stays flat.
- Electrodes: location from `brainRegions` (CA1), `channel_id` 0-based, the lab's theta, ripple and bad channels.
  Devices are the probes of session.mat; groups are the .xml electrode groups.
- HERD: species (NCBITaxon:10116), sex (PATO:0000384), CA1 (UBERON:0003881), cell types (CL:0000598 pyramidal,
  CL:0000099 interneuron). MeaningsTables for the trial cooling states and sides, the cooling intervals and the sleep
  states; HED only for the sleep states (Awake, Asleep).
