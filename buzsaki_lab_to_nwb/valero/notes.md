
Random notes


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

So, there is a TTL and there is a camera.

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