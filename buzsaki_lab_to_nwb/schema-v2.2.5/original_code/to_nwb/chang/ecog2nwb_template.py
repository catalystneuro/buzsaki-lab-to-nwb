from datetime import datetime

import numpy as np
import pandas as pd
from nwbext_ecog.ecog_manual import CorticalSurfaces, ECoGSubject
from pynwb import NWBFile, TimeSeries, NWBHDF5IO, get_manager
from pynwb.ecephys import ElectricalSeries
from pytz import timezone
from scipy.io.wavfile import read as wavread

# get_manager must come after dynamic imports
manager = get_manager()

external_subject = True

nwbfile = NWBFile('session description', 'session identifier',
                  datetime.now().astimezone(), institution='UCSF',
                  lab='Chang Lab')

# electrodes
devices = ['a', 'a', 'a', 'b', 'b', 'b']
locations = ['a location', 'b location']
udevices, inds = np.unique(devices, return_inverse=True)
groups = []
for device_name, location in zip(udevices, locations):
    # Create devices
    device = nwbfile.create_device(device_name)

    # Create electrode groups
    electrode_group = nwbfile.create_electrode_group(
        name=device_name + '_electrodes',
        description=device_name,
        location=location,
        device=device)
    groups.append(electrode_group)

nwbfile.add_electrode_column('bad', 'whether the electrode is too noisy to use')

electrodes_df = pd.DataFrame(
    {'location': ['c', 'c', 'c', 'd', 'd', 'd'],
     'group': np.array(groups)[inds],
     'x': [np.nan] * 6,
     'y': [np.nan] * 6,
     'z': [np.nan] * 6,
     'imp': [np.nan] * 6,
     'filtering': ['none'] * 6,
     'bad': [False] * 5 + [True]}
)

for _, row in electrodes_df.iterrows():
    nwbfile.add_electrode(**{label: row[label] for label in electrodes_df})

all_elecs = nwbfile.create_electrode_table_region(
        list(range(len(electrodes_df))), 'all electrodes')


# ECoG signal
ecog_signal = np.random.randn(1000, 64)
ecog_ts = ElectricalSeries('ECoG', ecog_signal, all_elecs, rate=3000.,
                           description='ecog_signal', conversion=0.001)


nwbfile.add_acquisition(ecog_ts)

# Trials
# optional columns
nwbfile.add_trial_column('condition', 'condition of task')
nwbfile.add_trial_column('response_latency', 'in seconds')
nwbfile.add_trial_column('response', 'y is yes, n is no')
nwbfile.add_trial_column('bad', 'whether a trial is bad either because of '
                                'artifact or bad performance')

trials_df = pd.DataFrame({'start_time': [1., 2., 3.],
                          'stop_time': [1.5, 2.5, 3.5],
                          'condition': ['a', 'b', 'c'],
                          'response_latency': [.3, .26, .31],
                          'response': ['y', 'n', 'y'],
                          'bad': [False, False, True]})

for _, row in trials_df.iterrows():
    nwbfile.add_trial(**{label: row[label] for label in trials_df})

# print(nwbfile.trials.to_dataframe())

# bad times
bad_times_data = [[5.4, 6.],
                  [10.4, 11.]]  # in seconds
for start, stop in bad_times_data:
    nwbfile.add_invalid_time_interval(start_time=start,
                                      stop_time=stop,
                                      tags=('ECoG artifact',),
                                      timeseries=ecog_ts)

# Create units table for neurons from micro-array recordings
single_electrode_regions = [
    nwbfile.create_electrode_table_region([i], 'electrode i')
    for i in range(len(electrodes_df))]

all_spike_times = [[1., 2., 3., 4.],
                   [2., 3., 4.],
                   [0.5, 1., 4., 10., 15.]]

all_electrodes = ((0,), (0,), (1,))

waveform_means = [np.random.randn(30, 1) for _ in range(3)]

for spike_times, electrodes, waveform_mean in \
        zip(all_spike_times, all_electrodes, waveform_means):
    nwbfile.add_unit(spike_times=spike_times,
                     electrodes=electrodes,
                     waveform_mean=waveform_mean)

# analog data
# microphone data
# Be careful! This might contain identifying information
mic_path = '/Users/bendichter/Desktop/Chang/video_abstract/word_emphasis.wav'
mic_fs, mic_data = wavread(mic_path)
nwbfile.add_acquisition(
    TimeSeries('microphone', mic_data, 'audio unit', rate=float(mic_fs),
               description="audio recording from microphone in room")
)
# all analog data can be added like the microphone example (speaker, button press, etc.)
spk_path = '/Users/bendichter/Desktop/Chang/video_abstract/word_emphasis.wav'
spk_fs, spk_data = wavread(spk_path)
nwbfile.add_stimulus(
    TimeSeries('speaker1', spk_data, 'audio unit', rate=float(spk_fs),
               description="speaker recording")
)

subject = ECoGSubject(species='homo sapiens', age='PY21', sex='M')

cortical_surfaces = CorticalSurfaces()
for name in ('a', 'b', 'c'):
    vertices = np.random.randn(10, 3)
    faces = np.random.randint(0, 9, (15, 3))
    cortical_surfaces.create_surface(name=name, faces=faces, vertices=vertices)
subject.cortical_surfaces = cortical_surfaces

# cortical surfaces
if external_subject:
    subject_fpath = 'S1.nwbaux'
    subject_nwbfile = NWBFile(
        session_description='session description', identifier='S1', subject=subject,
        session_start_time=datetime(1900, 1, 1).astimezone(timezone('UTC')))
    with NWBHDF5IO(subject_fpath, manager=manager, mode='w') as subject_io:
        subject_io.write(subject_nwbfile)
    subject_read_io = NWBHDF5IO(subject_fpath, manager=manager, mode='r')
    subject_nwbfile = subject_read_io.read()
    subject = subject_nwbfile.subject

nwbfile.subject = subject

fout_path = 'ecog_example.nwb'
with NWBHDF5IO(fout_path, manager=manager, mode='w') as io:
    io.write(nwbfile)

# test read
with NWBHDF5IO(fout_path, 'r') as io:
    io.read()

if external_subject:
    subject_read_io.close()
