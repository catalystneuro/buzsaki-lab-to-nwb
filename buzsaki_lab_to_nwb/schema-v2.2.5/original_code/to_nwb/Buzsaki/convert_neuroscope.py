import os
from datetime import datetime

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject

import numpy as np

from tqdm import tqdm

import to_nwb.neuroscope as ns

session_path = '/Users/bendichter/Desktop/Buzsaki/datasets/McKenzieS/camkii4/20160817'

stub = True

subject_path, session_id = os.path.split(session_path)
subject_id = os.path.split(subject_path)[1]


nwbfile = NWBFile(session_description='session_description',
                  identifier=subject_id + '_' + session_id,
                  session_start_time=datetime.now().astimezone(),
                  file_create_date=datetime.now().astimezone(),
                  experimenter='experimenter',
                  session_id=session_id,
                  institution='NYU',
                  lab='lab',
                  related_publications='pubs')

nwbfile.subject = Subject(subject_id=subject_id, species='Mus musculus')

ns.write_electrode_table(nwbfile, session_path)
ns.add_lfp(nwbfile, session_path, stub=stub)

ns.write_events(nwbfile, session_path)

ns.add_units(nwbfile, session_path)

nshanks = len(ns.get_shank_channels(session_path))
for shankn in tqdm(np.arange(nshanks)+1, desc='processing each shank'):

    ns.write_spike_waveforms(nwbfile, session_path, shankn)
    ns.write_unit_series(nwbfile, session_path, shankn)

out_fname = session_path
if stub:
    out_fname += '_stub'
out_fname += '.nwb'

with NWBHDF5IO(out_fname, 'w') as io:
    io.write(nwbfile)

#  test read
with NWBHDF5IO(out_fname, 'r') as io:
    io.read()


