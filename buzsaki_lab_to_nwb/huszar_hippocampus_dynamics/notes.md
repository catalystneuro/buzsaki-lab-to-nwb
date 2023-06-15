
### Some useful information. 
The link to the [paper](https://www.researchgate.net/publication/360752155_Preconfigured_dynamics_in_the_hippocampus_are_guided_by_embryonic_birthdate_and_rate_of_neurogenesis)


Peter Petersen, one of the members of the Buzsaki lab, has shared with us the following documents that contain the structure of the cell explorer format:

* [new format](https://cellexplorer.org/data-structure/)
* [old format](https://github.com/buzsakilab/buzcode/wiki/Data-Formatting-Standards)

He referred to the old format as buzcode.

## To ask the authors
Something confusing. For the session `e13_16f1_210302`.

The value in `session.mat` of the date is `2011-08-18`. 
But on the other hand for the same session the detection date in `SleepState.mat` is `2021-04-11"` which one should be followed?

Are the units in `SleepState` in seconds? The timestamps then correspond to a recording of around 5 hours.


## Todo
* In the paper the birthdates are marked as: E13.5, E14.5, E15.5, and E16.5
This means embrionic age (E) apparently. How does it track with the recent changes on age representation on nwb. Here, maybe use gestational age.
* The matlab files do not seem to contain a `sessionInfo` which is a requirement for using `CellExplorerSortingExtractor` from spikeinterface. Maybe they change the way that they do it, maybe it is lost. Probably better to ask them. In case they don't, it should be straighforward to roll a new
sorting extractor for this dataset.

## Important information from the paper

### Subjects
Time-pregnant C57BL/6J female mice 
were either bred in-house or obtained from Charles River Laboratory. Timed pregnancies were
prepared by co-housing males and females shortly before the dark cycle. Early morning of the
next day was considered embryonic (E) age 0.5. Time pregnant mice and their offspring were
kept on a regular light-dark cycle. Electrode-implanted adult mice (3-6 months) were housed
individually on a reverse light-dark cycle. 

### Behavior
A subset of n=8 mice (E13.5, n=1; E14.5, n=2; E15.5, n=2; E16.5, n=3) was trained on a spatial
alternation task in a figure-8 maze. Animals were water restricted before the start of experiments
and habituated to a custom-built 79x79cm figure-8 maze (Fig. 6A) raised 61cm above the
nd.88 678 Over 3-5 days following the start of water deprivation, animals were shaped to
alternate arms between trials to receive a water reward in the first corner reached after making a
correct left/right turn. A 5-s delay in the start area was introduced between trials. The length of
each trial was 205 cm. IR sensors were used to detect the animal's progression through the task,
and 3D printed doors mounted to servo motors were opened/closed to prevent the mice from
backtracking (Fig. 6A). IR sensors and servo motors were controlled by a custom Arduino-based
circuit.88 684 The position of head-mounted red LEDs was tracked with an overhead Basler camera
(acA1300-60 gmNIR, Graftek Imaging) at a frame rate of 30Hz, and tracking data was aligned to
the recording via TTL pulses from the camera, as well as a slow pulsing LED located outside of
the maze. Animals were required to run at least 10 trials along each arm (at least 20 trials total)
within each session. In all sessions that included behavior, animals spent ~120min in the
homecage prior to running on the maze, and another ~120 minutes in the homecage after. All
behavioral sessions were performed in the mornings