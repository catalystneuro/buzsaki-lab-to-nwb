import os
import pandas as pd
from ndx_miniscope import Miniscope
from pynwb import NWBFile, NWBHDF5IO
from datetime import datetime
from dateutil.tz import tzlocal
from pynwb.image import ImageSeries
from natsort import natsorted
from glob import glob


def load_miniscope_timestamps(fpath, cam_num=1):
    if not fpath[-4:] == '.dat':
        fpath = os.path.join(fpath, 'timestamp.dat')
    df = pd.read_csv(fpath, sep='\t')
    df_cam = df[df['camNum'] == cam_num]
    tt = df_cam['sysClock'].values/1000
    tt[0] = 0

    return tt


data_dir = '/Volumes/black_backup/data/Soltesz/example_miniscope'

settings_and_notes_file = os.path.join(data_dir, 'settings_and_notes.dat')

df = pd.read_csv(settings_and_notes_file, sep='\t').loc[0]

session_start_time = datetime(2017, 4, 15, 12, tzinfo=tzlocal())

nwb = NWBFile('session_description', 'identifier', session_start_time)

miniscope = Miniscope(name='Miniscope', excitation=int(df['excitation']),
                      msCamExposure=int(df['msCamExposure']),
                      recordLength=int(df['recordLength']))

nwb.add_device(miniscope)

ms_files = [os.path.split(x)[1] for x in
            natsorted(glob(os.path.join(data_dir, 'msCam*.avi')))]

behav_files = [os.path.split(x)[1] for x in
               natsorted(glob(os.path.join(data_dir, 'behavCam*.avi')))]

nwb.add_acquisition(
    ImageSeries(
        name='OnePhotonSeries',
        format='external',
        external_file=ms_files,
        timestamps=load_miniscope_timestamps(data_dir),
        starting_frame=[0] * len(ms_files)
    )
)

nwb.add_acquisition(
    ImageSeries(
        name='behaviorCam',
        format='external',
        external_file=behav_files,
        timestamps=load_miniscope_timestamps(data_dir, cam_num=2),
        starting_frame=[0] * len(behav_files)
    )
)

save_path = os.path.join(data_dir, 'test_out.nwb')
with NWBHDF5IO(save_path, 'w') as io:
    io.write(nwb)

# test read
with NWBHDF5IO(save_path, 'r') as io:
    nwb = io.read()
