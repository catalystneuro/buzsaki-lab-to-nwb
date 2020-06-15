import os
from pynwb import NWBFile, NWBHDF5IO
from pynwb.ecephys import LFP, ElectricalSeries

from scipy.io import loadmat
import numpy as np

import pandas as pd

from datetime import datetime

# missing:
# session_start_time


def isdigit(x):
    return x in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']


def parse_electrode_label(label):
    device_name = ''.join([x for x in label if not isdigit(x)])
    number = ''.join([x for x in label if isdigit(x)])

    return device_name, number


nwbfile = NWBFile(session_description='resting state ECoG',
                  identifier='0',
                  session_start_time=datetime(1900, 1, 1),
                  file_create_date=datetime.now().astimezone(),
                  experimenter='Stephan Bickel',
                  institution='',
                  lab='Bickel')

basepath = '/Users/bendichter/Dropbox/NWB/'
matpath = os.path.join(basepath, 'restECoG_example.mat')

matin = loadmat(matpath)

ftrip = matin['ecog']['ftrip'][0][0]

lfp = ftrip['trial'][0][0][0][0].T
lfp_rate = float(ftrip['fsample'])

channel_labels = np.array([x[0][0] for x in matin['ecog']['mgrid_labels'][0][0]])
device_labels, device_nums = zip(*(parse_electrode_label(x) for x in channel_labels))

lepto_path = os.path.join(basepath, 'LIJ082_JeMi.LEPTO')
df = pd.read_csv(lepto_path, skiprows=2, names=('x', 'y', 'z'), sep=' ')
electrode_positions = np.array(df)

this_device = 'start'
for i, (device_label, label, (x, y, z)) in enumerate(zip(device_labels,
                                                         channel_labels,
                                                         electrode_positions)):
    if not (device_label == this_device):
        this_device = device_label
        device = nwbfile.create_device(device_label)
        electrode_group = nwbfile.create_electrode_group(name=device_label + ' electrode group',
                                                         description=' ',
                                                         device=device,
                                                         location='unknown')

    nwbfile.add_electrode(i, x, y, z, imp=np.nan, location='unknown',
                          filtering='unknown', description=label,
                          group=electrode_group)

electrode_table_region = nwbfile.create_electrode_table_region(
    list(range(len(electrode_positions))), 'all ECoG electrodes')

nwbfile.add_acquisition(
    LFP(electrical_series=ElectricalSeries(
            'lfp', 'lfp signal for all electrodes', lfp,
            electrode_table_region, starting_time=0.0, rate=lfp_rate)))

with NWBHDF5IO('resting_state.nwb') as io:
    io.write(nwbfile)

