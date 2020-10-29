# Notes on GrosmarkAD of buzsaki-lab-to-nwb data mapping
## Open questions for Ben or Peter are in []

### NWBFile
* datetext information for the session_start_time is in the session_id string.

### Subject
Most information able to be found in the publication and added manually. Male wildtype Long Evans rats between 250-350g.


### Position (processed, not acquisition)
No .whl file is found, at least in the prototype set.
All positional information is contained in a single position.behavior.mat file, unlike the multiple position files that Yuta had.

This .mat file has a single variable named 'position'. This variable is a struct with several relevant fields.
* position.behaviorinfo.MazeType contains the name of the maze used for the experiment, and is used as the name for the position and spatial series.
* position.timestamps contains the timestamps of the positional information. I confirmed manually it is regularly sampled and so only the starting time and rate are used in the SpatialSeries.
* position.samplingRate contains the sampling frequency of the timestamps in Hz.
* position.position contains three fields; x, y, and lin. x and y are certainly the corresponding coordinates of the subject. All fields are aligned one-to-one with the timestamps. [What is the 'lin' field and should it be included? Currently only capturing the (x,y) values.]
 
[The (x,y) series are interspersed with NaN values, indicating a likelihood of multiple trials; but no explicit trial information can be found in the folder. Should we infer the trial information based on discontinuities in these series?]
 
### Intervals
See "Position" section for details on structure of that file.

*position.Epochs contains the names and windows for the experimental eepochs.
*[See question in "Position" section regarding inference of trial windows]


### LFP
Standard Neuroscope format for LFP data and waveforms. No reference electrodes used and hence no decomposition series.


### Sorted units
Standard Neuroscope format for sorted spiking units. Cell types and brain region are contained in session_id.CellClass.cellinfo.mat (CellClass.label) and session_id.spikes.cellinfo.mat (spikes.region), respectively.


### Recording information
No .dat files are available in any of the GrosmarkAD set.
.xml contains electrode structure used to create device and electrode groups.

[There is also a special hand-written .pdf which specifies certain electrodes that were ignored due to "low-amplitude" and "instability". Should we therefore ignore these electrodes and their corresponding data within all the NWBFiles?]


