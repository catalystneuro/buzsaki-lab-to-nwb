from datetime import datetime

from pynwb import NWBFile, NWBHDF5IO

from to_nwb.general import CatTimeSeries

nwbfile = NWBFile(source='source',
                  session_description='mouse in open exploration and theta maze',
                  identifier='id',
                  session_start_time=datetime.now(),
                  file_create_date=datetime.now(),
                  experimenter='Yuta Senzai',
                  session_id='fname',
                  institution='NYU',
                  lab='Buzsaki',
                  related_publications='DOI:10.1016/j.neuron.2016.12.011')

ts = CatTimeSeries(data=[0, 1, 1, 2], rate=1., name='behavior',
                   source='source', values=['a', 'b', 'c'])

nwbfile.add_acquisition(ts)


with NWBHDF5IO('test_cat_ts', mode='w') as io:
    io.write(nwbfile)
