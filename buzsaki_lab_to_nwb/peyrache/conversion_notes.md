# Peyrache et al. 2015 (DANDI:000056, CRCNS th-1): conversion notes

Source: the Buzsaki lab share `PeyracheA/MouseNN/MouseNN-YYMMDD/` (the CRCNS th-1 sessions), the CRCNS session table
`crcns_th-1_session_info.xls`, and the LFP of the session's file in DANDI:000056 version 0.250624.0430 (the share has
no `.eeg` files). Triage of the earlier conversion:
[issue 77](https://github.com/catalystneuro/buzsaki-lab-to-nwb/issues/77).

Run one session:

```
python -m buzsaki_lab_to_nwb.peyrache.convert_session PeyracheA/Mouse12/Mouse12-120807 out.nwb \
    --session-info crcns_th-1_session_info.xls --published sub-Mouse12_ses-Mouse12-120807_behavior+ecephys.nwb
```

## What goes where

| NWB | Source |
|---|---|
| `units` | clusters 2 and up of every `.clu.N`/`.res.N` (sorted spike times, 1/20000 s resolution), keyed by shank and cluster. Columns: `shank`, `cluster_id`, `region` (electrode group location), `in_lab_cell_list` (`Analysis/SpikeData.mat`), `lratio`/`mahalanobis_distance`/`isi_index` (`GeneralInfo.mat`), `hd_*` and `is_hd_cell` (`HDCells.mat hdCellStats`), `buzcode_region` (`spikes.cellinfo.mat`), `cell_type` (`CellClass.cellinfo.mat`, pE/pI), `lab_mean_waveform` (`SpikeData.mat meanWaveF`, Mouse12/17 only), `buzcode_mean_waveform` (`spikes.cellinfo.mat rawWaveform`), `max_waveform_channel` |
| electrodes, electrode groups | one group per `.xml` anatomical group; location from `GeneralInfo.mat shankStructure` in Allen CCF names (HERD to UBERON); probe depth from the CRCNS table; `bad_channel` from `sessionInfo.mat` |
| `processing/ecephys/LFP` | the published LFP, unchanged, with the published scaling |
| `intervals/epochs` | `Analysis/BehavEpochs.mat` intervalSets (0.1 ms units), tagged; `intervals/sub_recordings` from `DatSegments.txt` and `.srs` |
| `processing/behavior/sleep_states` | the paper's `.states.SWS/REM/Wake` (seconds); `sleep_states_buzcode` is the 2019 `SleepState.states.mat` used by the earlier files |
| `acquisition/{red,blue}_led_position_pixels` | `.whl`, camera pixels, -1 to NaN |
| `processing/behavior/position` | `.pos` (cm, written with conversion 0.01 to m), read leniently (Mouse17-130201 has 2 malformed lines) |
| `processing/behavior/head_direction` | `.ang` (radians); checked: `.ang = angle(red - blue in .pos) - angOffset (mod 2 pi)` in Mouse12-120807/08 and Mouse24-131216 |
| `processing/ecephys/down_states`, `hd_down_states`, `ripples` | `.evt.dow`, `.evt.hdD`, `.evt.rip` (+ power and frequency from `.sts.RIPPLES`), with the detection parameters of the lab's code in `RunAnalysisLog.mat` |

`.pos`/`.ang` are also looked for in the mouse folder (Mouse25-140131/140204 keep them there).

## Things to know

- The `.clu` file numbers (spike groups, the lab's `shank`) and the `.xml` anatomical groups (the numbering of
  `shankStructure` and of the `.xml` description) differ in Mouse12-120807/08 (spike group 13 is anatomical group 14,
  the CA1 wires) and in Mouse20. Units are matched to electrode groups by their channels.
- The lab's cell list is every cluster 2 and up on the shanks it chose; quality and HD statistics exist only for it.
- The waveform units are not documented (probably ADC steps).
- LFP gain: the earlier conversion used 0.3815 uV per step (Amplipex); the `.xml` gives 20 V and x1000. Not documented.
- Subject age is not given anywhere (the paper says adult, 27-50 g); sex is 5 male and 2 female mice, not per mouse.
- Mouse12-120808: position/spike clock mismatch in sub-recording 03, and its wake epoch is the radial maze (as in the
  paper's Methods); noted in the file, data kept as given.
- Light stimulation (`_optoStim.mat`) is not part of the paper and is not converted.
