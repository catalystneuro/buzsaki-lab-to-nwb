import os

from datetime import datetime
import numpy as np

from pynwb import NWBFile, NWBHDF5IO, TimeSeries
from pynwb.ecephys import ElectricalSeries, LFP
from pynwb.misc import UnitTimes
from hdmf.data_utils import DataChunkIterator
from tqdm import tqdm
from hdmf.backends.hdf5 import H5DataIO

from brpylib import NevFile

WRITE_ALL_LFPS = False


fpath = '/Users/bendichter/Desktop/Movshon/data/Data_BlackRock_MWorks_forBenDichter/HT_V4_Textures2_200stimoff_180716_001'
fpath_base, fname = os.path.split(fpath)
fpath = '/Users/bendichter/Desktop/Movshon/data/Data_BlackRock_MWorks_forBenDichter/HT_V4_Textures2_200stimoff_180716_001'
nev_path = fpath + '.nev'
ns_path = fpath + '.ns6'
identifier = fname

NevFile(nev_path)


source = fname
nwbfile = NWBFile(source=source,
                  session_description=' ',
                  identifier=identifier,
                  session_start_time=datetime.now(),
                  file_create_date=datetime.now(),
                  experimenter='Gerick',
                  session_id=fname,
                  institution='NYU',
                  lab='Movshon',
                  related_publications='')

all_ts = []

print('setting up electrodes...', end='', flush=True)

fpath = '/Users/bendichter/Desktop/Movshon/data/Data_BlackRock_MWorks_forBenDichter/HT_V4_Textures2_200stimoff_180716_001'
nev_path = fpath + '.nev'
ns_path = fpath + '.ns6'
nev_file = NevFile(nev_path)
elecs = [(int(x['ElectrodeID']), x['Label'] )
         for x in nev_file.extended_headers
         if ('ElectrodeID' in x) and ('Label' in x)]


electrode_counter = 0
device_name = 'device'
device = nwbfile.create_device(device_name, 'source')
elec_electrode_group = nwbfile.create_electrode_group(
    name=device_name + '_electrodes',
    source=fname + '.xml',
    description=device_name,
    device=device,
    location='unknown')

# special electrodes
device_name = 'analog'
device = nwbfile.create_device(device_name, 'analog')
ainp_electrode_group = nwbfile.create_electrode_group(
    name=device_name + '_electrodes',
    source='source',
    description=device_name,
    device=device,
    location='unknown')

ut = UnitTimes(name='spikes', source=source)
elec_inds = []
for i, (elec_id, elec_label) in tqdm(enumerate(elecs)):
    if elec_label[:4] == 'ainp':
        electrode_group = ainp_electrode_group
    else:
        electrode_group = elec_electrode_group
        elecs_data = nev_file.getdata([elec_id])
        spikes = (np.array(elecs_data['spike_events']['TimeStamps'][0]) / 30000).tolist()
        elec_inds.append(i)
        ut.add_spike_times(elec_id, spikes)
    nwbfile.add_electrode(
        elec_id,
        np.nan, np.nan, np.nan,  # position?
        imp=np.nan,
        location='unknown',
        filtering='unknown',
        description='description',
        group=electrode_group)


all_table_region = nwbfile.create_electrode_table_region(
    elec_inds, 'all_electrodes')
print('done.')

# lfp
print('reading LFPs...', end='', flush=True)

print('done.')

print('making ElectricalSeries objects for LFP...', end='', flush=True)
all_lfp_electrical_series = ElectricalSeries(
    'all_lfp',
    'lfp signal for all shank electrodes',
    data,
    all_table_region,
    conversion=np.nan,
    starting_time=0.0,
    rate=lfp_fs,
    resolution=np.nan)
all_ts.append(all_lfp_electrical_series)
all_lfp = nwbfile.add_acquisition(LFP(name='all_lfp', source='source',
                                      electrical_series=all_lfp_electrical_series))
print('done.')

electrical_series = ElectricalSeries(
    'reference_lfp',
    'signal used as the reference lfp',
    gzip(all_channels[:, lfp_channel]),
    lfp_table_region,
    conversion=np.nan,
    starting_time=0.0,
    rate=lfp_fs,
    resolution=np.nan)

lfp = nwbfile.add_acquisition(LFP(source='source', name='reference_lfp',
                                  electrical_series=electrical_series))
all_ts.append(electrical_series)

# create epochs corresponding to experiments/environments for the mouse
task_types = ['OpenFieldPosition_ExtraLarge', 'OpenFieldPosition_New_Curtain',
              'OpenFieldPosition_New', 'OpenFieldPosition_Old_Curtain',
              'OpenFieldPosition_Old', 'OpenFieldPosition_Oldlast', 'EightMazePosition']

module_behavior = nwbfile.create_processing_module(name='behavior',
                                                   source=source,
                                                   description=source)
for label in task_types:
    print('loading normalized position data for ' + label + '...', end='', flush=True)
    file = os.path.join(fpath, fname + '__' + label)

    matin = loadmat(file)
    tt = matin['twhl_norm'][:, 0]
    pos_data = matin['twhl_norm'][:, 1:3]

    exp_times = find_discontinuities(tt)

    spatial_series_object = SpatialSeries(name=label + '_spatial_series',
                                          source='position sensor0',
                                          data=gzip(pos_data),
                                          reference_frame='unknown',
                                          conversion=np.nan,
                                          resolution=np.nan,
                                          timestamps=gzip(tt))
    pos_obj = Position(source=source,
                       spatial_series=spatial_series_object,
                       name=label + '_position')

    module_behavior.add_container(pos_obj)

    for i, window in enumerate(exp_times):
        nwbfile.create_epoch(start_time=window[0], stop_time=window[1],
                             tags=tuple(), description=label + '_' + str(i),
                             timeseries=all_ts+[spatial_series_object])
    print('done.')

## load celltypes
matin = loadmat(os.path.join(fpath_base, 'DG_all_6__UnitFeatureSummary_add.mat'),
                struct_as_record=False)['UnitFeatureCell'][0][0]

# taken from ReadMe
celltype_dict = {
    0: 'unknown',
    1: 'granule cells (DG) or pyramidal cells (CA3)  (need to use region info. see below.)',
    2: 'mossy cell',
    3: 'narrow waveform cell',
    4: 'optogenetically tagged SST cell',
    5: 'wide waveform cell (narrower, exclude opto tagged SST cell)',
    6: 'wide waveform cell (wider)',
    8: 'positive waveform unit (non-bursty)',
    9: 'positive waveform unit (bursty)',
    10: 'positive negative waveform unit'
}

region_dict = {3: 'CA3', 4: 'DG'}

this_file = matin.fname == fname
celltype_ids = matin.fineCellType.ravel()[this_file]
region_ids = matin.region.ravel()[this_file]
unit_ids = matin.unitID.ravel()[this_file]

celltype_names = []
for celltype_id, region_id in zip(celltype_ids, region_ids):
    if celltype_id == 1:
        if region_id == 3:
            celltype_names.append('pyramidal cell')
        elif region_id == 4:
            celltype_names.append('granule cell')
        else:
            raise Exception('unknown type')
    else:
        celltype_names.append(celltype_dict[celltype_id])

u_cats, indices = np.unique(celltype_names, return_inverse=True)

cci_obj = CatCellInfo(name='CellTypes',
                      source='DG_all_6__UnitFeatureSummary_add.mat',
                      values=list(u_cats), indices=list(indices))

ut_obj = ns.build_unit_times(fpath, fname)

module_cellular = nwbfile.create_processing_module('cellular', source=source,
                                                   description=source)

module_cellular.add_container(ut_obj)
module_cellular.add_container(cci_obj)

trialdata_path = os.path.join(fpath, fname + '__EightMazeRun.mat')
trials_data = loadmat(trialdata_path)['EightMazeRun']

trialdatainfo_path = os.path.join(fpath, fname + '__EightMazeRunInfo.mat')
trialdatainfo = [x[0] for x in loadmat(trialdatainfo_path)['EightMazeRunInfo'][0]]


features = trialdatainfo[:7]
features[:2] = 'start', 'end'
[nwbfile.add_trial_column(x, 'description') for x in features]

for trial_data in trials_data:
    nwbfile.add_trial({lab: dat for lab, dat in zip(features, trial_data[:7])})

mono_syn_fpath = os.path.join(fpath, fname+'-MonoSynConvClick.mat')

matin = loadmat(mono_syn_fpath)
exc = matin['FinalExcMonoSynID']
inh = matin['FinalInhMonoSynID']

exc_obj = CatCellInfo('excitatory_connections', 'YutaMouse41-150903-MonoSynConvClick.mat',
                      values=[], cell_index=exc[:, 0] - 1, indices=exc[:, 1] - 1)
module_cellular.add_container(exc_obj)
inh_obj = CatCellInfo('inhibitory_connections', 'YutaMouse41-150903-MonoSynConvClick.mat',
                      values=[], cell_index=inh[:, 0] - 1, indices=inh[:, 1] - 1)
module_cellular.add_container(inh_obj)

sleep_state_fpath = os.path.join(fpath, fname+'--StatePeriod.mat')
matin = loadmat(sleep_state_fpath)['StatePeriod']

table = DynamicTable(name='states', source='source', description='sleep states of animal')
table.add_column(name='start', description='start time')
table.add_column(name='end', description='end time')
table.add_column(name='state', description='sleep state')

for name in matin.dtype.names:
    for row in matin[name][0][0]:
        table.add_row({'start': row[0], 'end': row[1], 'state': name})

module_behavior.add_container(table)


# compute filtered LFP

module_lfp = nwbfile.create_processing_module(
    'lfp_mod', source=source, description=source)

#filt_ephys = FilteredEphys(source='source', name='name')
for passband in ('theta',):# 'gamma'):
    lfp_fft = filter_lfp(all_channels[:, lfp_channel], np.array(lfp_fs), passband=passband)
    lfp_phase, _ = hilbert_lfp(lfp_fft)

    # I'd like to use ElectricalSeries here but links are broken in the processing module
    electrical_series = TimeSeries(name=passband + '_phase',
                                   source='ephys_analysis',
                                   data=lfp_phase,
                                   rate=lfp_fs,
                                   unit='radians')
    #electrodes=lfp_table_region)
    #filt_ephys.add_electrical_series(electrical_series)
    module_lfp.add_container(electrical_series)

#module_lfp.add_container(filt_ephys)




out_fname = '/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/test_spikes.nwb'
#out_fname = '/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/' + fname + '.nwb'
print('writing NWB file...', end='', flush=True)
with NWBHDF5IO(out_fname, mode='w') as io:
    #io.write(nwbfile, cache_spec=True)
    io.write(nwbfile)
print('done.')

print('testing read...', end='', flush=True)
# test read
# with NWBHDF5IO(out_fname, mode='r', load_namespaces=True) as io:
with NWBHDF5IO(out_fname, mode='r') as io:
    io.read()
print('done.')
