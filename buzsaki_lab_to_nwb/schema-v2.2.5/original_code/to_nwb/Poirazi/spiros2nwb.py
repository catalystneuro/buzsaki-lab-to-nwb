import os
import pickle
from datetime import datetime
from glob import glob
import re
import matplotlib.pyplot as plt
import numpy as np
from dateutil.tz import tzlocal
from pynwb import NWBFile, NWBHDF5IO, TimeSeries
from tqdm import tqdm
from hdmf.backends.hdf5.h5_utils import H5DataIO


def natural_key(text):
    # Key used for natural ordering: orders files correctly even if numbers are not zero-padded
    return [int(c) if c.isdigit() else c for c in re.split('(\d+)', text)]


run_dir = '/Users/bendichter/Desktop/Poirazi/data/DATA_Ben'
session_start_time = datetime(2017, 4, 15, 12, tzinfo=tzlocal())
description = 'description of session'
identifier = 'session_id'
COMPRESS = True


# setup NWB file

nwbfile = NWBFile(session_description=description,
                  identifier=identifier,
                  session_start_time=session_start_time)
nwbfile.add_unit_column('cell_type', 'cell type')
nwbfile.add_unit_column('cell_type_id', 'integer index within each cell type')


# convert continuous data (1 compartment per cell)

mp_data = []
for dat_file in tqdm(sorted(glob(os.path.join(run_dir, '*dat')), key=natural_key),
                     desc='reading .dat files'):
        mp_data.append(np.loadtxt(dat_file))
mp_data = np.column_stack(mp_data)
if COMPRESS:
    mp_data = H5DataIO(mp_data, compression='gzip')
ts = TimeSeries('membrane_potential', mp_data, unit='mV', rate=10000.)
nwbfile.add_acquisition(ts)


# convert spike data

for spk_file in sorted(glob(os.path.join(run_dir, 'spiketimes*'))):
    with open(spk_file, 'rb') as file:
        data = pickle.load(file)
    cell_type = spk_file.split('_')[-2]
    for row in data:
        cell_id = row[0]
        spikes = np.array(row[1:], dtype=np.float) / 1000
        nwbfile.add_unit(spike_times=spikes, cell_type=cell_type, cell_type_id=cell_id)

print(nwbfile.units['cell_type'].data)
print(nwbfile.units.get_unit_spike_times(21))


# write NWB file

with NWBHDF5IO(run_dir + '.nwb', 'w') as io:
    io.write(nwbfile)

# access data

read_io = NWBHDF5IO(run_dir + '.nwb', 'r')
nwbfile = read_io.read()


# get cell types
print(nwbfile.units['cell_type'].data)

# get spike times for one cell (in seconds)
print(nwbfile.units.get_unit_spike_times(21))

# read all data from 1st cell:
data = nwbfile.acquisition['membrane_potential'].data[:, 0]
unit = nwbfile.acquisition['membrane_potential'].unit
rate = nwbfile.acquisition['membrane_potential'].rate
plt.plot(np.arange(len(data))/rate, data)
plt.ylabel(unit)
plt.xlabel('time (s)')


# data is identical to old file
dat_file = sorted(glob(os.path.join(run_dir, '*dat')), key=natural_key)[0]
data2 = np.loadtxt(dat_file)
plt.plot(data)

print('data is equal: ' + str(np.all(data2 == data)))


# to read all data into memory (this takes 2 minutes reading the .dat files on my computer)
all_membrane_potential_data = nwbfile.acquisition['membrane_potential'].data[:]