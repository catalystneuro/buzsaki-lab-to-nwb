
# Notes
The following notes are taken from the paper and the supplementary material.
They are intended to clarify some of the decisions of the conversions and should work as a reference for the conversion and discussion and the authors.


## Important information in the paper


### Electrodes and recording devices


Animals were implanted with 32-site, 4 shank μLED probes ((15); Neurolight, MI) over the dorsal right
hippocampus (antero-posterior 2.0 mm, mediolateral 1.5 mm, dorsoventral 0.6 mm), as described
previously (44, 45).

This are the optical probes they use
https://www.neurolighttech.com/product

The fact sheet of thei probes is a good source of info:
https://www.neurolighttech.com/_files/ugd/63a305_28d96686c0ec4cc18b728b2c5c9b7d78.pdf

In particular, we know they use an `Intan RHD2132 Amplifier Board`. This is a 32 channel amplifier.

Juding by the description in the paper, they were using the chronic variety:

> Probes were mounted on microdrives that were advanced to CA1 pyramidal layer in small increments over 5 to 8 days,
while depth distribution of LFPs (SPW-R events and theta oscillations) and unit firing were used
to identify CA1 pyramidal layer. After implantation, all animals were housed individually

### LFP
> . Electrophysiological data were acquired using an Intan
RHD2000 system (Intan Technologies LLC) digitized with 30 kHz rate. The wide-band signal
was downsampled to 1.25 kHz and used as the LFP signa

The LFP sampling rate should be 1.25 KhZ

### Optogenetics
> we recorded and probed large numbers of CA1 pyramidal neurons simultaneously in freely moving calcium/calmodulin–dependent protein kinase II alpha (CamKIIα) -Cre::Ai32 mice

### Intracellular recording

There should be 4 sessions with intracelluar recordings. They are described in the paper as follows:

> Mice (n=4) were implanted with titanium head plates (41) and 50-μm stainless steel ground
wire was implanted between the skull and dura over the cerebellum. A ~200 µm diameter
craniotomy was made, and the dura was removed over dorsal hippocampus (antero-posterior 2.0
mm, mediolateral 1.5 mm). The craniotomy was covered with Kwik-Sil (World Precision
Instruments) until the day of recording. Mice were habituated to head fixation over one week and
were allowed to run on top of a 15 cm diameter wheel during fixation. On the day of recording,
the Kwik-Sil was removed, and sharp pipettes were pulled from 1.5 mm/0.86 mm outer/inner
diameter borosilicate glass (A-M Systems) on a Flaming-Brown puller (Sutter Instruments) and
filled with 1.5 M potassium acetate and 2% Neurobiotin (wt/vol, Vector Labs). In vivo pipette
impedances varied from 40-90 MΩ. Intracellular recording were performed blindly, and the
micropipette was driven by a robotic manipulator (Sutter MP-285). Signals were acquired with
an intracellular amplifier (Axoclamp 900A) at 100× gain. 

### Behavior

Paper description:
> Animals were housed on a 12-hour reverse light/dark cycle, and the recording session
started 1-2 hr after the onset of the dark phase. We recorded from the mice while they slept or
walked around freely in the home cage. Electrophysiological data were acquired using an Intan
RHD2000 system (Intan Technologies LLC) digitized with 30 kHz rate. The wide-band signal
was downsampled to 1.25 kHz and used as the LFP signal. 

I wonder if they have sleep vs awake as epochs of if they are different sessions.

> The animal’s position was monitored
with a Basler camera (acA1300-60 gmNIR, Graftek Imaging) sampling at 30Hz to detect a headmounted red LEDs. 
Position was synchronized with neural data with TTLs signaling shutter position. Animals were handled daily and accommodated to the experimenter, recording room
and cables for 1 week before the start of the experiments. 

So, there is a TTL and there is a camera. After some digging, I found that there is an `.avi` file located inside another directory and a corresponding `.mat` file.

> Water access was restricted and was
only available as reward on a linear track, ad libitum for 30 minutes at the end of each
experimental day and ad libitum for one full non-experimental day per week. Mice were trained
to run laps in a PVC linear track (110 cm long, 6.35 cm wide) to retrieve water reward (5-10µL)
at each end. Water delivery and optogenetic stimuli during track were controlled by a custommade, Arduino-based circuit (circuits and software are available in
https://github.com/valegarman). 

Information about behavioral task

> For a typical recording session, mice were recorded  continuously for ~300 min through 6 experimental blocks (see Fig. S7D): pre track-baseline
(Pre-baseline, 60 min), Pre-track stimulation (Pre-stim, 60 min), Linear Maze task, post trackstimulation (Post Stim) and Post-track baseline. During track running, 3 baseline (nostimulation) blocks (10 trials each) were interleaved with two stimulation blocks (40 to 60 trials).

This figure S7D is useful for understanding the epochs:

![Figure S7D](./images/figure_S7D.png)

# Questions
* Why is there two Tracking.Behaviors, the file is repeated in the folder that contains the video and in the top level.
* Why does this conversion combines data from the old and new format? We have both `sessionInfo.mat` and `session.mat`. I am puzzled by this.
* There is both kilosort and CellExplorer data. I think kilosort probably represents the final info to be added to the units table but probably should confirm this with the authors.
* They have a folder `revision_cell_metrics` that contains cell_metric data ordered by data. Same question as above.
* Are there 4 mice for interacellular recordings and 4 mice for extracellular recordings? I think so but I am not sure.
* The organization of the folder structure in globus is cofusing. We have some sessions that are named `fCamk{number}` and I think they make sense. They refero to the optogenic protein / cell line. But I can't find the meaning of the following folder names and ctrl + f in the paper and the supplementy materials is not yielding any matches:
    * `fCr{number}`
    * `fld2Dlx{number}`
    * `Cck{number}`
    * `fNKx{number}`
    * `fPv{number}`
    * `fSst{number}`
    * `fVip{number}`
    * Plus a folder with `unindexed subjects`.

* Is this a typo one the figure 1: 
    > (M) Group results for five cells from five anesthetized rats (green) and five cells from four head-fixed mice (pink). 
    
    I could not find mention of intracellular recordings in rats in the material and methods. Ah no, here it is:

    Quote from methods:
    > (M) Group results for five cells from five anesthetized rats (green) and five cells from four head-fixed mice (pink). 

    So they do use another dataset for this from another paper.
* There are two tracking behaviors one on the top folder and another in the sub-folder. Do they indicate different experiments.


## Synchornization and times

For session `fCamk1_200827_sess9`
* The video is 30 minutes long.
* The auxiliary.dat files in the sub-folder with the movies are between 1 and 3 minutes. Not clear yet what they represent.
* LFP signal:
* Raw signal: 5 hours of recording. This matches wit the 300 minutes of recording in the paper. 
* Spiketimes:
* Timestamps for tracking behavior:
* Epochs: 
    We shoud have something like this according to the paper:
    * Pre-baseline: 60 minutes
    * Pre-stim: 60 minutes
    * Linear Maze: 60 minutes
    * Post-stim: 60 minutes
    * Post-baseline: 60 minutes

    It is strange that the movie is only 30 minutes. Maybe they only turn it on at specific points, could have halved the frequency. Need to ask.
