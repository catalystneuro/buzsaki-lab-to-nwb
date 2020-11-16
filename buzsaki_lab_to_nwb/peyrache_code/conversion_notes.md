# Notes on PeyracheA of buzsaki-lab-to-nwb data mapping
## Open questions for Ben or Peter are in straight braces []
## ToDo list items are in curley braces {}

Prototype dataset is Mouse12-120806

### NWBFile
datetext information for the session_start_time is in the session_id string. Format is equivalent to that of the Yuta conversion.

### Subject
{Find and add}


### Position (processed, not acquisition)
Raw acquisition .whl file is found, will be added as such.
No other processed position information found.

### Intervals
{Find and add}


### LFP
Standard Neuroscope format for LFP data and waveforms.

{check for reference electrodes}


### Sorted units
Standard Neuroscope format for sorted spiking units.

{check on extra cell metadata like cell types, region, etc.}


### Recording information
Sessions 120806, 120809, and 120810 of Mouse 12 all have shank-specific raw data, but it is only available on the crcns (not globus) so download will take some time. Also does not appear to include *all* of the shanks; 120806 has 7 shanks worth, the other two have only 6. Either way, will need a MultiRecordingExtractor to add these.

.xml contains electrode structure used to create device and electrode groups.


### Conversion notes

