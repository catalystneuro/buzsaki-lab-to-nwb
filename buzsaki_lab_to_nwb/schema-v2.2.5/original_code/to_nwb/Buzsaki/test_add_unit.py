from pynwb import NWBFile, NWBHDF5IO
from datetime import datetime


nwbfile = NWBFile('a', 'b', 'c', datetime.now(), datetime.now())

nwbfile.add_unit_column('excitatory_connections', 'ids of cells that receive excitatory input from cell')

nwbfile.add_unit({'id': 1, 'excitatory_connections': [1, 2]})
nwbfile.add_unit({'id': 2, 'excitatory_connections': [1, 2, 3]})

with NWBHDF5IO('test_unit.nwb', 'w') as io:
    io.write(nwbfile)
