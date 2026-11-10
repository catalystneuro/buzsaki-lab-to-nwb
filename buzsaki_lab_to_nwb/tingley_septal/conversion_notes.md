# Tingley and Buzsaki 2018 / 2020 (DANDI:000213, DANDI:000218)

Conversion with NeuroConv; the earlier nwb-conversion-tools converter was replaced. One converter serves both
dandisets (`--dandiset` picks the paper's metadata). The fixes follow the triage in
https://github.com/catalystneuro/buzsaki-lab-to-nwb/issues/81 (000213) and
https://github.com/catalystneuro/buzsaki-lab-to-nwb/issues/82 (000218).

```
python -m buzsaki_lab_to_nwb.tingley_septal.convert_session TingleyD/DT8/20170207_144um_1944um_merge out.nwb \
    --dandiset 000213 --published <earlier DANDI file of the session> [--no-wideband] [--stub]
```

`valid_sessions.yml` (000213) and `valid_sessions_ripples.yml` (000218) list the sessions of each dandiset.

## Sources (Buzsaki lab Globus share, `TingleyD/<rat>/<session>/`)

- `<session>.xml`: channel and spike groups.
- `<session>.sessionInfo.mat` (v5 or v7.3): per-channel `region`, and the channel roles `thetaChans`, `lfpChans`,
  `ca1`, `ca3`, `ls`, `refChan` (0-based channels; checked against the event files' `rippleChan`).
- `<session>.spikes.cellinfo.mat` (buzcode): units with `UID`, `shankID`, `cluID`, `region`, `maxWaveformCh`,
  `rawWaveform`. Without it, the `.clu.N`/`.res.N` files. `<session>.isolationMetrics.cellinfo.mat` where present.
- `<session>.behavior.mat`: tracking, trials (`events.trialIntervals`, `trials{i}.direction/type/mapping`,
  `trialConditions`, `conditionType`, `map`). Its layout differs between rats (`units` in `behavior` or
  `behavior.position`; `errorPerMarker` in `behavior` or `behavior.behaviorinfo`), which `read_behavior` unifies.
- `<session>.SleepState.states.mat`: buzcode SleepScoreMaster states (also for DT8 and ecephys-only sessions, which the
  earlier conversion skipped).
- Event files: `ripplesALL/NREM/WAKE.event.mat`, `CA1Ripples.events.mat`, `LSRipples.events.mat`,
  `ls_ripples.event.mat` (bz_FindRipples, some v7.3) and `ripples_ls.mat` (n x 4: start, peak, stop, power).
- Recording subfolders `<...>_<YYMMDD>_<HHMMSS>` of merged sessions: the start time of the first recording.
- LFP and wide-band signal: the lab's `.lfp`/`.dat` files are not on the share, so they are taken from the session's
  file in the earlier dandiset version (`--published`). Those hold the int16 values as float32 with the electrodes in
  spike-group order; each block is checked to be whole int16 steps, cast back to int16 and put in channel order.

## Decisions

- Trials: rows sorted by start time together with their labels (the earlier files sorted only the rows, so about half
  of their `direction`/`trial_type` labels belong to another trial). Added `condition` (trialConditions),
  `condition_type`, and the lab's linearization (`linearized_position`, the 1-based template point of each sample,
  with its timestamps); the templates are in `processing/behavior/trial_conditions`. Trials listed twice in the source
  are kept, and the description says how many.
- Position: x, y, z from the source (2 columns for the LED rat DT2, whose z is empty); `unit` "meters" with
  conversion 1 or 0.001 for the source's `m`/`mm`; pixels stay pixels with conversion 1 (no scale in the source).
  Orientation quaternions are a TimeSeries with unit "dimensionless"; DT2's yaw is a CompassDirection in radians
  (its values lie in 0..pi). In DT2 0304 the yaw has 4(n-1)+1 values for n frames, so it is written at 4 times the
  frame rate, as interpolated by the lab between the first and last frame. OptiTrack timestamps that are regular at
  120 Hz (within 1 us) are written as a starting time and rate; others are kept as timestamps.
  `error_per_marker` has the position's unit (its values scale with it: ~1e-4 in m sessions, 0.1-11 in mm sessions).
- DT2 timestamps: every stored value equals round(i / 30 Hz, 5 significant digits), so they are rebuilt as i / 30 Hz
  (the Basler camera's rate in the paper). The lab's `samplingRate` (30.000331 for 0221, 29.999391 for 0304) is the
  frame count over the last rounded timestamp, and i / samplingRate does not reproduce the stored values (off by up
  to 0.73 s in 0221), so it is not used. The rebuild is applied only when it reproduces every stored value.
- Units: spike times sorted (the description lists the units that were unsorted in the source); `raw_waveform` is the
  lab's 32-sample mean waveform in the lab's (unstated) units, not `waveform_mean`, whose unit would be volts.
  Isolation metrics are the lab's values (L-ratios in the thousands, as stored).
- Electrodes: one row per channel in channel order; `location` from `sessionInfo.region` (`hpc` → hippocampal
  formation: the probe aimed at dorsal CA1, not resolved to a subfield), with the lab's label in `region`. Electrode
  groups are spike groups; probes are the runs of spike groups with the same region. The klusta `.prb` geometry is
  not written: every `.prb` places sites by list position with the same generic staggered layout for groups of 4, 8,
  10 and 12 sites (DT9 uses another), including the 4-site groups the earlier conversion called "reference sites a few
  millimeters dorsal".
- Events: one TimeIntervals table per event file in `processing/ecephys`, with peak time, normalized power, peak
  frequency and amplitude, and the detector, channels and parameters stored in each file in the description.
  `ripplesNREM`/`ripplesWAKE` are subsets of `ripplesALL` (same peaks), so they are boolean columns of `ripplesALL`.
- Sleep states: `processing/behavior/sleep_states` with labels WAKE, NREM, REM, MA; MeaningsTables with HED (`Awake`,
  `Asleep`; MA has a meaning only). Trial directions are clockwise/counter-clockwise, not left/right runs, so they have
  meanings and no HED.
- Subject: sex "U": the papers had 3 male and 2 female Long-Evans rats but do not say which was which. No age: the
  papers say only "adult", so nwbinspector reports the missing age as its one critical issue.
- Not converted: the lab's derived maps (placeFields, firingMaps, phaseMaps, olypherInfo, assemblies), `cat.evt`
  (Intan file-type boundaries, not epochs), and the DT2 `behav.mat`/`.pos`/`.led` files (the same rounded times).

## Open questions for the lab

- Which probe each depth of the session name belongs to, and its zero.
- Whether `hpc` means CA1 (sessionInfo.ca1 is on the hpc probe in newer sessions).
- The DT2 pixel scale, and the clock of DT2's trialIntervals: they differ from the 30 Hz frame times of their first
  samples by up to 1 s (0221), while the frame times reproduce every stored position timestamp.
- DT9 0501: the trials' positions differ from the session tracking at the same times.
- DT8 0207 LSRipples.events.mat says rippleChan 25, but the LFP stored with the detection is channel 20.
- ripplesALL.event.mat of DT5 1007 stores NREM `restrict` intervals although its events span the whole session.
- The detection parameters stored with the events differ from the papers' methods (120-200 Hz, 2/5 SD, 15-250 ms).
- The units of `rawWaveform`; whether the >50 Hz clusters are multi-unit; the paper's unit inclusion criteria.
- DT5 1007 SleepState.states.mat scores 5-7419 s as REM (50 REM bouts against 19 NREM), which looks like a scoring
  error; kept as stored.
- The sex and age of each rat; the hardware reference; the position of the 4-site groups; the source of position outliers.
