import re
from datetime import datetime
from glob import glob

import numpy as np
from pynwb import TimeSeries, NWBFile, NWBHDF5IO
from tqdm import tqdm

files = glob('/Users/bendichter/Desktop/Poirazi/data/Sample_Data/*.dat')


def natural_keys(text):
    return [int(text) if text.isdigit() else text for _ in re.split('(\d+)', text)]


files.sort(key=natural_keys)
data = []
for file in tqdm(files, desc='reading .dat files'):
    data.append(np.loadtxt(file))
data = np.column_stack(data)

ts = TimeSeries('membrane_potential', data, unit='mV', rate=np.nan)
nwbfile = NWBFile(session_description='description of session',
                  identifier='simulation_run_id',
                  session_start_time=datetime.now().astimezone())
nwbfile.add_acquisition(ts)

with NWBHDF5IO('example_data.nwb', 'w') as io:
    io.write(nwbfile)
