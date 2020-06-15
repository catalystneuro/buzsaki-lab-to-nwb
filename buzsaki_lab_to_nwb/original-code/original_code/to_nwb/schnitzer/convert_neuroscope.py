import os
import numpy as np
from to_nwb.neuroscope import get_lfp_sampling_rate, get_channel_groups

from pynwb.ecephys import ElectricalSeries, LFP
from pynwb import NWBFile, NWBHDF5IO, TimeSeries
from dateutil.parser import parse as parse_date

from pytz import timezone

"""
Time simply increments by 1
"""

session_path = '/Users/bendichter/Desktop/Schnitzer/data/test1_171207_181558'
this_dir = session_path.split('/')[-1]
name, day, time = this_dir.split('_')

session_start_time = parse_date(day, yearfirst=True)
session_start_time = session_start_time.replace(tzinfo=timezone('US/Pacific'))

amp_xml_path = os.path.join(session_path, 'amplifier.xml')
amp_fs = get_lfp_sampling_rate(xml_filepath=amp_xml_path)
nchannels = len(get_channel_groups(xml_filepath=amp_xml_path)[0])


datas = ['amplifier', 'time', 'auxiliary', 'supply']
data_fpaths = {name: os.path.join(session_path, name + '.dat') for name in datas}

amp_data = np.fromfile(data_fpaths['amplifier'], dtype=np.int16).reshape(-1, nchannels)
time_data = np.fromfile(data_fpaths['time'], dtype=np.int32)
supply_data = np.fromfile(data_fpaths['supply'], dtype=np.int16)
ntt = len(amp_data)
aux_data = np.fromfile(data_fpaths['auxiliary'], dtype=np.int16).reshape(ntt, -1)

nwbfile = NWBFile(session_start_time=session_start_time, identifier=this_dir,
                  session_description='unknown')

device = nwbfile.create_device(name='Neuronexus Probe Buzsaki32/H32Package')
group = nwbfile.create_electrode_group(name='all_channels_group',
                                       description='all channels',
                                       device=device,
                                       location='unknown')

for i in range(nchannels):
    nwbfile.add_electrode(np.nan, np.nan, np.nan,  # position
                          imp=np.nan,
                          location='unknown',
                          filtering='unknown',
                          group=group)
electrode_table_region = nwbfile.create_electrode_table_region(
    list(range(nchannels)), 'all electrodes')


electrical_series = ElectricalSeries(data=amp_data,
                                     rate=amp_fs,
                                     electrodes=electrode_table_region,
                                     name='amp_data')
nwbfile.add_acquisition(LFP(name='amp_data', electrical_series=electrical_series))
nwbfile.add_acquisition(TimeSeries('auxiliary', data=aux_data, rate=amp_fs, unit='na'))
nwbfile.add_acquisition(TimeSeries('supply', data=supply_data, rate=amp_fs, unit='na'))

out_fname = this_dir + '.nwb'
with NWBHDF5IO(out_fname, 'w') as io:
    io.write(nwbfile)
