import os
from datetime import datetime
from glob import glob
import re
import matplotlib.pyplot as plt
import numpy as np
from dateutil.tz import tzlocal
from pynwb import NWBFile, NWBHDF5IO
from tqdm import tqdm
from hdmf.backends.hdf5.h5_utils import H5DataIO
from nwbext_simulation_output import CompartmentSeries, create_ragged_array


def natural_key(text):
    # Key used for natural ordering: orders files correctly even if numbers are not zero-padded
    return [int(c) if c.isdigit() else c for c in re.split('(\d+)', text)]


run_dir = '/Users/bendichter/Desktop/Poirazi/data/AlexandraDataSample/HIPP'
session_start_time = datetime(2017, 4, 15, 12, tzinfo=tzlocal())
description = 'description of session'
identifier = 'session_id'
COMPRESS = True

# setup NWB file

nwbfile = NWBFile(session_description=description,
                  identifier=identifier,
                  session_start_time=session_start_time)
nwbfile.add_unit_column('compartment_labels', 'cell compartment labels for each cell')

mp_data = []
all_compartments = []
cell_paths = sorted(glob(os.path.join(run_dir, '*')), key=natural_key)
for cell_path in cell_paths:
    cell_id = os.path.split(cell_path)[1]
    compartment_labels = []
    all_compartments.append([])
    compartment_paths = sorted(glob(os.path.join(cell_path, '*.txt')), key=natural_key)
    for i, txt_file in enumerate(tqdm(compartment_paths, desc='reading .txt files for ' + cell_id)):
        label_pieces = os.path.split(txt_file)[1].split('_')
        if label_pieces[0] == 'soma':
            compartment_label = 'soma'
        else:
            compartment_label = label_pieces[1] + '_' + label_pieces[2]
        compartment_labels.append(compartment_label)

        all_compartments[-1].append(i)
        mp_data.append(np.loadtxt(txt_file))
    nwbfile.add_unit(compartment_labels=compartment_labels)

mp_data = np.column_stack(mp_data)
if COMPRESS:
    mp_data = H5DataIO(mp_data, compression='gzip')
compartments, compartments_index = create_ragged_array(all_compartments)
cs = CompartmentSeries('membrane_potential', mp_data, unit='mV', rate=np.nan, compartments=compartments,
                       compartments_index=compartments_index, unit_id=np.arange(len(cell_paths), dtype=int))
nwbfile.add_acquisition(cs)

with NWBHDF5IO(run_dir + '.nwb', 'w') as io:
    io.write(nwbfile)


# read data
io_read = NWBHDF5IO(run_dir + '.nwb', 'r')
nwbfile = io_read.read()

