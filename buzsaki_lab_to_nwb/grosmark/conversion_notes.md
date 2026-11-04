# Grosmark and Buzsaki 2016 (DANDI:000044, CRCNS hc-11)

Conversion with NeuroConv; the earlier nwb-conversion-tools converter was replaced. The fixes follow the triage in
https://github.com/catalystneuro/buzsaki-lab-to-nwb/issues/76.

```
python -m buzsaki_lab_to_nwb.grosmark.convert_session GrosmarkAD/Gatsby/Gatsby_08282013 out.nwb [--clu-res DIR] [--published FILE] [--stub]
```

## Sources (Buzsaki lab Globus share, `GrosmarkAD/<rat>/<session>/`)

- `<session>_sessInfo.mat`: the lab's file of the CRCNS release (MATLAB v7.3 for some sessions, v5 for others).
  Units (`Spikes.SpikeTimes`, `SpikeIDs` = spike group x 100 + cluster, `PyrIDs`, `IntIDs`), position
  (`Position.TwoDLocation`, `OneDLocation`, `TimeStamps`, `MazeType`) and epochs (`Epochs.PRE/Maze/POSTEpoch` and the
  lab's 5-state scoring `Wake/Drowsy/NREM/Intermediate/REM`). The buzcode files of 2019 were made from it.
- `<session>.xml`: channel groups, spike groups and the `skip` flags (`bad_electrode`).
- `<session>.eeg`: all channels at 1250 Hz, int16. Channels 0-127 are the probes; 128-133 (Buddy 128-131) the neck
  EMG and accelerometer (`_extra/Channel_Orderings.pdf`, `MISC_CHANNELS` in `grosmarkutils.py`). Without the .eeg the
  LFP can be taken from the earlier DANDI file (`--published`), which holds channels 0-127 of the .eeg unchanged.
- `<session>.SleepState.states.mat`: buzcode's automatic 3-state scoring of 2019 (the states of the earlier files).
- `position_info.mat` (linear-track sessions): laps (`pos_inf.in_eps/out_eps/ts_ep`).
- `<session>.clu.N`/`.res.N` (optional): each unit's spikes are checked to be its cluster's.
- `<rat>151/<rat>151_<date>_presleep.meta` (Achilles only): start time of the PRE recording, the session start time.
- `_extra/crcns_hc-11_data_description.pdf`, `Channel_Orderings.pdf`, `Sessions_Recordings_Summary.pdf`: the
  documentation used for the descriptions.

## Decisions

- Scaling: 0.3815 uV per step (Amplipex KJE-1001, +-5 V, 16 bits, x400 in the .meta files). The .xml files' 20 V and
  x1000 are not used. The EMG and accelerometer are written in raw steps (`a.u.`): their gain is not documented.
- Electrode groups are named by probe and shank (`left_shank1` ... `right_extra_sites`); `spike_group` keeps the
  lab's 1-based number. The 4 extra sites of the Buzsaki64sp probes (Achilles, Cicero; spike groups 7 and 14) have
  location `unknown`: they are 1.25-5 mm above the tip of shank 4, above CA1.
- No x/y/z: the only geometry files are buzcode's generic layouts (`AnimalMetadata.WithinProbeXYLocations` in the
  probes' pin order, `chanCoords` for Achilles_10252013, which places the extra sites 10 um apart), neither of which
  maps to the lab's rearranged channel order. Whether channels run from the tip upward is not documented.
- Units keep the lab's SpikeIDs as ids; the earlier files' `shank_id` (cluster - 2) and `global_id` are dropped.
- Gatsby_08022013: POST is kept at the lab's 30,413.6 s with a note that the recording continues to 32,002.4 s.
- Achilles_11012013: one REM bout of the lab's scoring has zero length ([13281, 13281] s); kept.
- Subject: no weight (only the 250-350 g range is known) and no age (the lab recorded none).
- Position rate: from the timestamps (~39.0626 Hz), not their period.

## Open questions for the lab

- The true end of POST in Gatsby_08022013, and what the last ~1,589 s are.
- The age of the rats.
- The camera frame orientation (whether linearized position on the circular maze increases clockwise in the room).
- Which end of each linear track (in the room) is linearized position 0, where the 'in' laps start.
- The site geometry in the lab's channel order, and depths; the location of the extra sites.
- The EMG and accelerometer gains and the accelerometer axes.
- Wide-band data for the MAZE epochs and for Buddy, Gatsby and Cicero; the paper's derived data and code.
