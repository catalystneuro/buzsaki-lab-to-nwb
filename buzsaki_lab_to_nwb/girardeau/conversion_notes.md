# Girardeau et al. 2017 (DANDI:000061): conversion notes

Girardeau G, Inema I, Buzsáki G (2017) Reactivations of emotional memory in the hippocampus–amygdala system during
sleep. Nature Neuroscience 20:1634–1642, https://doi.org/10.1038/nn.4637.

Source: the Buzsaki lab share `GirardeauG/RatNN/RatNN-YYYYMMDD/`, with the rat folder `GirardeauG/RatNN/`
(`RecordingLocations.mat`, `sessions.mat` or `Sessions.mat`). Where the share has no `.lfp` file for a session (16 of
the 40 sessions, for example Rat08-20130710), the LFP is taken from the session's file in DANDI:000061 version 0.250624.0426, a local copy or its S3 URL
(streamed). Triage of the earlier conversion:
[issue 79](https://github.com/catalystneuro/buzsaki-lab-to-nwb/issues/79).

Run one session:

```
python -m buzsaki_lab_to_nwb.girardeau.convert_session GirardeauG/Rat08/Rat08-20130710 out/sub-Rat08_ses-Rat08-20130710.nwb \
    --published https://dandiarchive.s3.amazonaws.com/blobs/... [--no-wideband]
```

The `.mpg` files in the session folder are written as external files and hard-linked next to the output file.

## What goes where

| NWB | Source |
|---|---|
| electrodes, electrode groups | one group per `.xml` anatomical group of channels 0 to 159 (shank N = anatomical group N = `.clu.N`); `region` = the lab's code for the shank in `RecordingLocations.mat` (`shankInfo`, unchanged), `location` = the name the code stands for (probably Paxinos), HERD to UBERON where one term matches |
| `units` | clusters 2 and up of every `.clu.N`/`.res.N` (sorted, resolution 1/20000 s), with `shank`, `cluster_id`, `region` (as the electrodes); checked against `spikes.cellinfo.mat` where it exists |
| `processing/ecephys/LFP` | `.lfp` (or `.eeg`) of the session, or the published LFP (its columns are channels 0 to 159 in order, checked against the `.dat`), 0.3815 µV per step |
| `acquisition/ElectricalSeries` | `.dat`, or the published wide-band signal; optional (`--no-wideband`) |
| `intervals/epochs` | `.cat.evt` (ms there, seconds here), tagged with the epoch label |
| `intervals/trials` | laps: `-Laps.mat` (`LtoRlaps`, `RtoLlaps`, `Uturnlaps`) with `direction`, `lap_type` from `-LapType.mat` (`aplaps`, `safelaps`) and `epoch` |
| `intervals/running_bouts` | `-TrackRunTimes.mat` (`trackruntimes`): the earlier files' "trials" |
| `processing/behavior/position` | `.whl` of the session (two LEDs, pixels, 1250/32 Hz from t = 0, -1 to NaN) |
| `processing/behavior/sleep_states` | `-States.mat` (`wake`, `drowsy`, `sws`, `Rem`, whole seconds); `sleep_states_buzcode` from the 2019 `SleepState.states.mat` where present |
| `processing/ecephys/ripples`, `beta_events` | `.rip.evt`, `.bet.evt` start/peak/stop, with the number of the labels as `channel` ("probably the detection channel") |
| `events/rewards`, `events/air_puffs` | `.lrw.evt`/`.rrw.evt` (with `side`), `.puf.evt` |
| `acquisition/accelerometer`, `air_puff_input`, `left_reward_input`, `right_reward_input` | auxiliary inputs in raw int16 steps ("a.u."), from the `.lfp` (1250 Hz; or a published series or a `.dat` under 20 GB that holds all channels); channels from the `session.mat` channelTags (Rat08, Rat09; 1-indexed there) or the `.xml` description (Rat10; 0-indexed there); accelerometer columns are "axis 1 to 3" (no axis names in the source); the reward side of each line is found from its step at the `.lrw.evt`/`.rrw.evt` events |
| `acquisition/video_*` | the epoch's `.mpg` if it is in the session folder (only some are on the share), external file; frame times approximate: the frames (lines of the epoch's `.tsp`) spread evenly over the epoch |
| MeaningsTables + HED | `value_meanings.yaml`: sleep states (Awake / Drowsy / Asleep), lap direction (`(Run, Rightward)` / `(Run, Leftward)`), lap type and reward side (meaning only) |

## Fixes of the triage

- Epoch times were in ms; now seconds.
- Units 0 and 1 were merged in 10 files because `spike_times_index` was stored modulo 65,536; the units are rebuilt from
  `.clu`/`.res`, and the seven files without units now have them.
- Electrode and unit locations come from `RecordingLocations.mat`.
- Position, laps and Rat09's sleep states (`-States.mat`) are added; the running bouts are no longer called trials.
- Video timestamps were a frame counter at an assumed 30 fps (in ms, carried over between videos); they are not
  reused. Videos not on the share are not referenced.
- Ripples are an intervals table with a channel column, not stimulus AnnotationSeries.

## Things to know (open questions for the lab)

- Gain: 0.3815 µV per step is the `leastSignificantBit` of the lab's `session.mat` (Amplipex KJE-1001); the `.xml`
  settings (20 V, 16 bits, x1000) give 0.305 µV.
- The region codes look like Paxinos abbreviations; which make up the paper's "BLA" is not in the source. `den`, `ven`,
  `blv`, `bmp` and `plc01` have no UBERON term of their own and get no HERD reference.
- Rat09: `RecordingLocations.mat` puts shanks 17 to 20 (channels 128 to 159, no spike groups) in `hpc`, while the
  triage read `HistoSheet.ods` as listing no hippocampal shank, and there are no `.rip.evt` files for Rat09.
- Rat09-20140402: the 2020 buzcode `spikes.cellinfo.mat` labels shanks 1 to 4 'BMA' (RecordingLocations.mat: `bmp`) and
  shank 7 'VEn/BLA' (`ven`). The units table keeps RecordingLocations.mat and says so in its description.
- The published Rat09 files hold only channels 0 to 127 without 123 (the spike-group channels), so their LFP cannot be
  mapped by column order; the converter takes Rat09's LFP from the share's `.lfp` (and refuses a published file whose
  columns are fewer than the probe channels). Rat08's published LFP is channels 0 to 159 in order.
- The number in the ripple labels ("Ripple start 30") is probably the detection channel; `session.mat` tags channel 3
  (1-based) as the ripple channel, so this is not certain.
- The `.tsp` time column is -2147483648 on every line, so the video frame times are unknown.
- `-Laps.mat` `leftLimit`/`rightLimit` are not documented (they are not the pixel x of the track ends).
- The `06-water` epoch of some Rat08 sessions is not described in the paper.
- Age: 3 months, kept from the earlier files (not found in the lab's files); weight not converted.
- Auxiliary inputs cannot be converted for the 16 sessions with no `.lfp` on the share: their published files hold only
  the probe channels (160, 128 or 127 columns) and their `.dat` files are over 20 GB or missing (Rat08-20130710, 0711,
  0713, 0717, 0718, 0722; Rat09-20140326, 0404, 0407; Rat10-20140701, 0704, 0705; Rat11-20150316, 0328, 0331, 0403).
- Rat11: no `session.mat` channelTags, and the `.xml` description (copied from Rat10) puts the auxiliary inputs on
  channels 166 to 171 of a 166-channel recording, so they are not converted for any Rat11 session.
- Rat10: 172 channels, with "Hippo wires" on 160 to 165 by its `.xml`; the converter takes channels 0 to 159 as the
  probe electrodes, so those wires are not written (not yet tested on a Rat10 session).
- Rat09's `session.mat` channelTags are the same as Rat08's (even the ripple channel); the air-puff and reward lines
  were checked against the events in Rat09-20140402.
- Cell types: the lab's `RatNN-finalType.mat` covers all sessions of a rat with no session index; not converted.
