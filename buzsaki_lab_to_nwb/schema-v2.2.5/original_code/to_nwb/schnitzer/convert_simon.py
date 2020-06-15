from scipy.io import loadmat
from datetime import datetime

from pynwb.ecephys import ElectricalSeries
from pynwb import NWBFile, NWBHDF5IO
from pynwb.ogen import OptogeneticSeries

import numpy as np

fpath = '/Users/bendichter/Desktop/Schnitzer/data/eoPHYS_SS1anesthesia/converted_data.mat'
fname = 'ex_simon'
session_description = ''
identifier = fname
institution = 'Stanford'
lab = 'Schnitzer'
source = fname

matin = loadmat(fpath, struct_as_record=False)
data = matin['data'][0]
session_start_time = datetime(*(int(x) for x in data[0].abstime[0]))

nwbfile = NWBFile(session_description, identifier,
                  session_start_time, datetime.now(),
                  institution=institution, lab=lab)

device_name = 'ePhys'
device = nwbfile.create_device(device_name)
electrode_group = nwbfile.create_electrode_group(
    name=device_name + '_electrodes',
    source=fname + '.xml',
    description=device_name,
    device=device,
    location='unknown')

ephys_channel_names = ['LFP1', 'LFP2', 'LFP3', 'EEGfrontal', 'EEGparietal']
for i, name in enumerate(ephys_channel_names):
    nwbfile.add_electrode(i,
                          np.nan, np.nan, np.nan,  # position?
                          imp=np.nan,
                          location='unknown',
                          filtering='unknown',
                          description=name,
                          group=electrode_group)

ephys_table_region = nwbfile.create_electrode_table_region(list(range(5)), 'all ephys electrodes')

ophys_device = nwbfile.create_device('ophys_device', source=source)
ogen_site = nwbfile.create_ogen_site('oPhys', ophys_device,
                                     description='unknown',
                                     excitation_lambda='unknown',
                                     location='unknown')

module = nwbfile.create_processing_module(name='0', description=source)

for i, trial_data in enumerate(data):
    nwbfile.add_acquisition(
        ElectricalSeries('ePhys trial' + str(i),
                         gzip(trial_data.ephys[:, [0, 1, 2, 6, 7]]),
                         ephys_table_region,
                         timestamps=trial_data.time)
    )

    nwbfile.add_acquisition(
        OptogeneticSeries('oPhys trial' + str(i),
                          gzip(trial_data.tempo_data[:, [0, 6, 7]]),
                          ogen_site,
                          description='laser, reference, voltage',
                          timestamps=trial_data.time))

with NWBHDF5IO('/Users/bendichter/Desktop/Schnitzer/data/simon_out.nwb', 'w') as io:
    io.write(nwbfile)


    #trial_data.ephys
    #trial_data.time
    #trial_data.abstime
    #trial_data.events
    #trial_data.tempo_data



