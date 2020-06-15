import os

from datetime import datetime
import numpy as np
import h5py
from dateutil.tz import tzlocal


from pynwb import NWBFile, NWBHDF5IO
from pynwb.ecephys import ElectricalSeries
from pynwb.ophys import OpticalChannel, TwoPhotonSeries
from hdmf.backends.hdf5 import H5DataIO

from to_nwb.neuroscope import get_channel_groups
from to_nwb.Losonczy.lfp_helpers import loadEEG


NA = 'THIS REQUIRED ATTRIBUTE INTENTIONALLY LEFT BLANK.'
SHORTEN = False


fpath = '/Users/bendichter/Desktop/Losonczy/example_data'
fpath_base, fname = os.path.split(fpath)
identifier = fname
nwbfile = NWBFile('Example data from Sebi', identifier,
                  session_start_time=datetime(2017, 5, 4, tzinfo=tzlocal()),
                  institution='Columbia',
                  lab='Losonczy')

eeg_base_name = os.path.join(fpath, 'LFP', 'svr009_Day2_FOV1_170504_131823')
eeg_dict = loadEEG(eeg_base_name)

lfp_xml_fpath = eeg_base_name + '.xml'
channel_groups = get_channel_groups(xml_filepath=lfp_xml_fpath)
lfp_channels = channel_groups[0]
lfp_fs = eeg_dict['sampleFreq']
nchannels = eeg_dict['nChannels']

lfp_signal = eeg_dict['EEG'][lfp_channels, :].T

device = nwbfile.create_device('implant')
electrode_group = nwbfile.create_electrode_group(
    name='electrode_group',
    description='implant_electrodes',
    device=device,
    location='unknown')

for channel in channel_groups[0]:
    nwbfile.add_electrode(np.nan, np.nan, np.nan,  # position?
                          imp=np.nan,
                          location='unknown',
                          filtering='unknown',
                          group=electrode_group)


lfp_table_region = nwbfile.create_electrode_table_region(list(range(4)),
                                                         'lfp electrodes')

lfp_elec_series = ElectricalSeries('multielectrode_recording',
                                   H5DataIO(lfp_signal, compression='gzip'),
                                   lfp_table_region,
                                   conversion=np.nan,
                                   starting_time=0.0,
                                   rate=lfp_fs,
                                   resolution=np.nan)

nwbfile.add_acquisition(lfp_elec_series)


optical_channel = OpticalChannel(
    name='Optical Channel',
    description=NA,
    emission_lambda=np.nan)

imaging_h5_filepath = os.path.join(fpath, 'TSeries-05042017-001_Cycle00001_Element00001.h5')

with h5py.File(imaging_h5_filepath, 'r') as f:
    if SHORTEN:
        all_imaging_data = f['imaging'][:100, ...]
    else:
        all_imaging_data = f['imaging'][:]
    channel_names = f['imaging'].attrs['channel_names']
    elem_size_um = f['imaging'].attrs['element_size_um']

# t,z,y,x,c -> t,x,y,z,c
all_imaging_data = np.swapaxes(all_imaging_data, 1, 3)

# t,x,y,z,c -> c,t,(x,y,z)
all_imaging_data = np.rollaxis(all_imaging_data, 4)
nx, ny, nz = all_imaging_data.shape[-3:]

manifold = np.meshgrid(np.arange(nx)*elem_size_um[2],
                       np.arange(ny)*elem_size_um[0],
                       np.arange(nz)*elem_size_um[1])


imaging_plane = nwbfile.create_imaging_plane(
    name='my_imgpln',
    optical_channel=optical_channel,
    description='unknown',
    device=device, excitation_lambda=np.nan,
    imaging_rate=np.nan, indicator='GFP',
    location='unknown',
    manifold=np.array([]),
    conversion=1.0,
    unit='um',
    reference_frame='A frame to refer to')

for channel_name, imaging_data in zip(channel_names, all_imaging_data):
    image_series = TwoPhotonSeries(name='TwoPhotonSeries' + channel_name.decode(),
                                   dimension=[2],
                                   data=H5DataIO(imaging_data, compression='gzip'),
                                   imaging_plane=imaging_plane,
                                   starting_frame=[0], timestamps=[1, 2, 3],
                                   scan_line_rate=np.nan,
                                   pmt_gain=np.nan)
    nwbfile.add_acquisition(image_series)

if SHORTEN:
    out_fname = fpath + '_stub.nwb'
else:
    out_fname = fpath + '.nwb'

print('writing NWB file...', end='', flush=True)
with NWBHDF5IO(out_fname, mode='w') as io:
    io.write(nwbfile)
print('done.')

print('testing read...', end='', flush=True)
# test read
with NWBHDF5IO(out_fname, mode='r') as io:
    io.read()
print('done.')
