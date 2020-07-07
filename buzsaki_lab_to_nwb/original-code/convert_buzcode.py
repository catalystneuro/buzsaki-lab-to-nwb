import os

from pathlib import Path
import numpy as np
from scipy.io import loadmat
from dateutil.parser import parse as dateparse
import pandas as pd

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject
from pynwb.behavior import SpatialSeries, Position
from pynwb.ecephys import ElectricalSeries

from hdmf.backends.hdf5.h5_utils import H5DataIO

from to_nwb import neuroscope as ns

WRITE_ALL_LFPS = False

# get sessionInfo

fpath = '/Users/bendichter/dev/buzcode/exampleDataStructs/fbasename'

fpath_base, fname = os.path.split(fpath)

session_info_matin = loadmat(
    '/Users/bendichter/dev/buzcode/exampleDataStructs/20170505_396um_0um_merge.sessionInfo.mat',
    struct_as_record=True)
date_text = session_info_matin['sessionInfo']['Date'][0][0][0]


animal_info_matin = loadmat(
    os.path.join(fpath_base, fname + '.animalMetaData.mat'),
    struct_as_record=True)

keys = ('ID', 'strain', 'species', 'surgeryDate')
animal_info = {key: animal_info_matin['animal'][key][0][0][0] for key in keys}

session_start_time = dateparse(date_text, yearfirst=True)


subject = Subject(subject_id=animal_info['ID'],
                  strain=animal_info['strain'],
                  species=animal_info['species'])

if 'DOB' in animal_info and type(animal_info['DOB']) is not str:
    subject.age = str(session_start_time - animal_info['DOB'])

nwbfile = NWBFile(session_description='mouse in open exploration and theta maze', identifier=fname,
                  session_start_time=session_start_time,
                  institution='NYU', lab='Buzsaki', subject=subject)

all_ts = []

xml_filepath = os.path.join(fpath_base, fname + '.xml')

print(xml_filepath)
channel_groups = ns.get_channel_groups(xml_filepath)
shank_channels = ns.get_shank_channels(xml_filepath)
nshanks = len(shank_channels)
all_shank_channels = np.concatenate(shank_channels)
nchannels = sum(len(x) for x in channel_groups)
lfp_fs = ns.get_lfp_sampling_rate(xml_filepath)

lfp_channel = 0  # value taken from Yuta's spreadsheet

my_whl_file = os.path.join(fpath_base, fname + '.whl')

my_behavior_file = os.path.join(fpath_base, fname + '.sessionInfo.mat')

if os.path.isfile(my_whl_file):
    pos_df = ns.add_position_data(nwbfile, fname)
elif os.path.isfile(my_behavior_file):
    bI = loadmat(os.path.join(fpath_base, fname + '.behavior.mat'), struct_as_record=True)

    # date_text = np.array2string(bI['behavior']['position'][0][0])

    # date_text = date_text[2:-2];
    d = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=d)

print('done.')

print('setting up electrodes...', end='', flush=True)
ns.write_electrode_table(nwbfile, fpath)
# shank electrodes
device = nwbfile.create_device('implant', fname + '.xml')
electrode_counter = 0
for shankn, channels in enumerate(shank_channels):
    electrode_group = nwbfile.create_electrode_group(
        name='shank{}'.format(shankn),
        description=fname,
        device=device,
        location='unknown')
    for channel in channels:
        nwbfile.add_electrode(np.nan, np.nan, np.nan,  # position?
                              imp=np.nan,
                              location='unknown',
                              filtering='unknown',
                              description='electrode {} of shank {}, channel {}'.format(
                                  electrode_counter, shankn, channel),
                              group=electrode_group)

        if channel == lfp_channel:
            lfp_table_region = nwbfile.create_electrode_table_region(
                [electrode_counter], 'lfp electrode')

        electrode_counter += 1

all_table_region = nwbfile.create_electrode_table_region(
    list(range(electrode_counter)), 'all electrodes')
print('done.')

# lfp
print('reading LFPs...', end='', flush=True)

my_lfp_file = Path(os.path.join(fpath_base, fname + '.lfp'))
my_eeg_file = Path(os.path.join(fpath_base, fname + '.eeg'))
lfp_file = 1
if my_lfp_file.is_file():
    lfp_file = os.path.join(fpath_base, fname + '.lfp')
elif my_eeg_file.is_file():
    lfp_file = os.path.join(fpath_base, fname + '.eeg')

if isinstance(lfp_file, str):

    # this needs to be rewritten to
    # 1) pull the number of channel (here hard coded as N = 80), from the XML
    # 2) load in chunks so you don't overwhelm the RAM

    all_channels = np.fromfile(lfp_file, dtype=np.int16).reshape(-1, 80)
    all_channels_lfp = all_channels[:, all_shank_channels]
    print('done.')

    if WRITE_ALL_LFPS:
        print('making ElectricalSeries objects for LFP...', end='', flush=True)
        lfp = nwbfile.add_acquisition(
            ElectricalSeries('lfp',
                             'lfp signal for all shank electrodes',
                             H5DataIO(all_channels_lfp, compression='gzip'),
                             all_table_region,
                             conversion=np.nan,
                             starting_time=0.0,
                             rate=lfp_fs,
                             resolution=np.nan))
        all_ts.append(lfp)
        print('done.')

module_behavior = nwbfile.create_processing_module(name='behavior',
                                                   description='contains behavioral data')

out_fname = fname + '.nwb'
print('writing NWB file...', end='', flush=True)
with NWBHDF5IO(out_fname, mode='w') as io:
    io.write(nwbfile, cache_spec=False)
print('done.')

print('testing read...', end='', flush=True)
# test read
with NWBHDF5IO(out_fname, mode='r') as io:
    io.read()
print('done.')
