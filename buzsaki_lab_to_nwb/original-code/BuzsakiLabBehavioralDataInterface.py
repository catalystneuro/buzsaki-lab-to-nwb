
from nwb_conversion_tools.utils import get_base_schema, get_schema_from_hdmf_class
from nwb_conversion_tools.BaseDataInterface import BaseDataInterface
from pynwb import NWBFile, TimeSeries
from pynwb.file import TimeIntervals
from pynwb.behavior import SpatialSeries,Position
from pynwb.ecephys import ElectricalSeries, LFP, SpikeEventSeries
from pynwb.misc import DecompositionSeries, AnnotationSeries
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator
import os
import pandas as pd
import numpy as np
from scipy.io import loadmat
from tqdm import tqdm
from glob import glob
from copy import deepcopy
from pathlib import Path
from typing import Union
# TODO: there doesn't seem to be a pypi for ephys_analysis... copy entire library here or just these functions?
from ephys_analysis.band_analysis import filter_lfp, hilbert_lfp

PathType = Union[str, Path, None]


def add_position_data(nwbfile, session_path, position_sensor_info, fs):
    '''
    Read raw position sensor data from .whl file

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str
    fs: float
        sampling rate (in units seconds) of regularly sampled series
    names: iterable
        names of column headings
    '''
    session_id = os.path.split(session_path)[1]
    whl_path = os.path.join(session_path, session_id + '.whl')
    
    if not os.path.isfile(whl_path):
        print('Warning: File not found (' + whl_path + ')!')
        return
    
    special_sensor_colnames = ()
    for position_sensor in position_sensor_info:
        special_sensor_colnames+=(position_sensor['colnames'][0],position_sensor['colnames'][1])
        
    df = pd.read_csv(whl_path, sep='\t', names=special_sensor_colnames)
    
    #TODO: some error checking on this
    for position_sensor in position_sensor_info:
        nwbfile.add_acquisition(
            SpatialSeries(position_sensor['name'],
                          H5DataIO(df[[position_sensor['colnames'][0], position_sensor['colnames'][1]]].values,
                                   compression='gzip'),
                          reference_frame=position_sensor['reference_frame'],
                          description=position_sensor['description'],
                          rate = fs,
                          starting_time = 0.,
                          resolution=np.nan))


def read_lfp(session_path: PathType, n_channels: int, lfp_sampling_rate: float,
             n_bits: int, stub_test: bool = False):
    '''
    Parameters
    ----------
    session_path: PathType
    stub: bool, optional
        Default is False. If True, don't read full LFP, but instead a 
        truncated version of at most size (50, n_channels)
        
    Returns
    -------
    lfp_fs, all_channels_data
    '''
    fpath_base, fname = os.path.split(session_path)
    #TODO: some error checking on this
    lfp_filepath = os.path.join(session_path, fname + '.eeg')
    
    if stub_test:
        max_size = 50
        all_channels_data = np.fromfile(lfp_filepath,
                                        dtype='int'+str(n_bits),
                                        count = max_size*n_channels).reshape(-1, n_channels)
    else:
        all_channels_data = np.fromfile(lfp_filepath,
                                        dtype='int'+str(n_bits)).reshape(-1, n_channels)
    return all_channels_data


def check_module(nwbfile, name, description=None):
    '''
    Check if processing module exists. If not, create it. Then return module
    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    name: str
    description: str | None (optional)
    
    Returns
    -------
    pynwb.module
    '''
    if name in nwbfile.modules:
        return nwbfile.modules[name]
    else:
        if description is None:
            description = name
        return nwbfile.create_processing_module(name, description)


def write_lfp(nwbfile, data, fs, name='LFP', description='local field potential signal', electrode_inds=None):
    '''
    Add LFP from neuroscope to a "ecephys" processing module of an NWBFile

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    data: array-like
    fs: float
    name: str
    description: str
    electrode_inds: list(int)

    Returns
    -------
    LFP pynwb.ecephys.ElectricalSeries
    '''

    if electrode_inds is None:
        if nwbfile.electrodes is not None and data.shape[1] <= len(nwbfile.electrodes.id.data[:]):
            electrode_inds = list(range(data.shape[1]))
        else:
            electrode_inds = list(range(len(nwbfile.electrodes.id.data[:])))

    table_region = nwbfile.create_electrode_table_region(
        electrode_inds, 'electrode table reference')

    data = H5DataIO(
        DataChunkIterator(
            tqdm(data, desc='writing lfp data'),
            buffer_size=int(fs * 3600)), compression='gzip')

    lfp_electrical_series = ElectricalSeries(
        name=name, description=description,
        data=data, electrodes=table_region, conversion=np.nan,
        rate=fs, resolution=np.nan)

    ecephys_mod = check_module(
        nwbfile, 'ecephys', 'intermediate data from extracellular electrophysiology recordings, e.g., LFP')

    if 'LFP' not in ecephys_mod.data_interfaces:
        ecephys_mod.add_data_interface(LFP(name='LFP'))

    ecephys_mod.data_interfaces['LFP'].add_electrical_series(lfp_electrical_series)

    return lfp_electrical_series


def read_spike_times(session_path, shankn, fs=20000.):
    '''
    Read .res files to get spike times

    Parameters
    ----------
    session_path: str | path
    shankn: int
        shank number (1-indexed)
    fs: float
        sampling rate. default = 20000.

    Returns
    -------
    '''
    _, session_name = os.path.split(session_path)
    timing_file = os.path.join(session_path, session_name + '.res.' + str(shankn))
    timing_df = pd.read_csv(timing_file, names=('time',))

    return timing_df.values.ravel() / fs


def write_spike_waveforms(nwbfile: NWBFile, session_path: PathType, shankn: int,
                          spikes_nsamples: int, stub_test: bool = False, 
                          compression: str = 'gzip'):
    '''
    Parameters
    ----------
    nwbfile: pynwb.NWBFiles
    session_path: str
    shankn: int
    stub_test: bool, optional
        default: False
    compression: str (optional)
    '''
    session_name = os.path.split(session_path)[1]
    spk_file = os.path.join(session_path, session_name + '.spk.' + str(shankn))
    if not os.path.isfile(spk_file):
            print('Warning: Spike waveforms for shank{} not found!'.format(shankn))
            return

    group = nwbfile.electrode_groups['shank' + str(shankn)]
    elec_idx = list(np.where(np.array(nwbfile.ec_electrodes['group']) == group)[0])
    table_region = nwbfile.create_electrode_table_region(elec_idx, group.name + ' region')

    nchan = len(elec_idx)

    if stub_test:
        max_size = 50
        spks = np.fromfile(spk_file,
                           dtype=np.int16,
                           count=max_size*spikes_nsamples*nchan).reshape(-1, spikes_nsamples, nchan)
        spike_times = read_spike_times(session_path, shankn).reshape(spks.size)
    else:
        spks = np.fromfile(spk_file,
                           dtype=np.int16).reshape(-1, spikes_nsamples, nchan)
        spike_times = read_spike_times(session_path, shankn)
        
    if compression:
        data = H5DataIO(spks, compression=compression)
    else:
        data = spks

    spike_event_series = SpikeEventSeries(name='SpikeEventSeries' + str(shankn),
                                          data=data,
                                          timestamps=spike_times,
                                          electrodes=table_region)


    #if 'shank' + str(shankn) in nwbfile.electrode_groups:
    #    nwbfile.electrode_groups['shank' + str(shankn)].event_waveform = EventWaveform(
    #        spike_event_series=spike_event_series)

    check_module(nwbfile, 'ecephys').add_data_interface(spike_event_series)
    
    
def get_events(session_path, suffixes=None):
    '''
    Parameters
    ----------
    session_path: str
    suffixes: Iterable(str), optional
        The 3-letter names for the events to write. If None, detect all in session_path
    '''
    session_name = os.path.split(session_path)[1]

    # TODO: add error checking here
    if suffixes is None:
        evt_files = glob(os.path.join(session_path, session_name) + '.evt.*') + \
                    glob(os.path.join(session_path, session_name) + '.*.evt')
    else:
        evt_files = [os.path.join(session_path, session_name + s)
                     for s in suffixes]

    out = []
    for evt_file in evt_files:
        parts = os.path.split(evt_file)[1].split('.')
        if parts[-1] == 'evt':
            name = '.'.join(parts[1:-1])
        else:
            name = parts[-1]
        df = pd.read_csv(evt_file, sep='\t', names=('time', 'desc'))
        if len(df):
            timestamps = df.values[:, 0].astype(float) / 1000
            data = df['desc'].values
            annotation_series = AnnotationSeries(name=name, data=data, timestamps=timestamps)
            out.append(annotation_series)
    return out


def find_discontinuities(tt, factor=10000):
    """
    Find discontinuities in a timeseries. Returns the indices before each discontinuity.
    """
    dt = np.diff(tt)
    before_jumps = np.where(dt > np.median(dt) * factor)[0]

    if len(before_jumps):
        out = np.array([tt[0], tt[before_jumps[0]]])
        for i, j in zip(before_jumps, before_jumps[1:]):
            out = np.vstack((out, [tt[i + 1], tt[j]]))
        out = np.vstack((out, [tt[before_jumps[-1] + 1], tt[-1]]))
        return out
    else:
        return np.array([[tt[0], tt[-1]]])
        
    
class BuzsakiLabBehavioralDataInterface(BaseDataInterface):

    @classmethod
    def get_input_schema(cls):
        return {}
    
    
    def __init__(self, **input_args):
        super().__init__(**input_args)
    
    def get_metadata_schema(self):
        metadata_schema = deepcopy(get_base_schema())
        
        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['SpatialSeries'] = get_schema_from_hdmf_class(SpatialSeries)
        required_fields = ['SpatialSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)
        
        return metadata_schema
    
    
    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict,
                     stub_test: bool = False, include_spike_waveforms: bool = False):
        # TODO: check/enforce format?
        session_path = "D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903"
        all_shank_channels = metadata_dict['shank_channels']
        special_electrode_dict = metadata_dict['special_electrodes']
        lfp_channel = metadata_dict['lfp_channel']
        nshanks = metadata_dict['nshanks']
        task_types = metadata_dict['task_types']
        spikes_nsamples = metadata_dict['spikes_nsamples']
        n_channels = metadata_dict['n_channels']
        lfp_sampling_rate = metadata_dict['lfp_sampling_rate']
        n_bits = metadata_dict['n_bits']
        fs = lfp_sampling_rate / spikes_nsamples
        position_sensor_info = metadata_dict['position_sensor_info']
        
        subject_path, session_id = os.path.split(session_path)
        fpath_base = os.path.split(subject_path)[0]
        
        add_position_data(nwbfile, session_path, position_sensor_info, fs)
        
        all_channels_lfp_data = read_lfp(session_path, n_channels=n_channels,
                                         lfp_sampling_rate=lfp_sampling_rate,
                                         n_bits=n_bits, stub_test=stub_test)
        lfp_data = all_channels_lfp_data[:, all_shank_channels]
        lfp_ts = write_lfp(nwbfile, lfp_data, lfp_sampling_rate,
                           name=metadata_dict['lfp']['name'],
                           description=metadata_dict['lfp']['description'])
        
        # TODO: error checking on format?
        for special_electrode in special_electrode_dict:
            ts = TimeSeries(name=special_electrode['name'],
                            description=special_electrode['description'],
                            data=all_channels_lfp_data[:, special_electrode['channel']],
                            rate=lfp_sampling_rate, unit='V',
                            resolution=np.nan)
            nwbfile.add_acquisition(ts)
    
        all_lfp_phases = []
        for passband in ('theta', 'gamma'):
            lfp_fft = filter_lfp(lfp_data[:, all_shank_channels == lfp_channel].ravel(), lfp_sampling_rate, passband=passband)
            lfp_phase, _ = hilbert_lfp(lfp_fft)
            all_lfp_phases.append(lfp_phase[:, np.newaxis])
        decomp_series_data = np.dstack(all_lfp_phases)
    
        # TODO: technically, not tested; also might be replaced with the new doubly jagged features?
        if include_spike_waveforms:
            for shankn in np.arange(nshanks, dtype=int) + 1:
                write_spike_waveforms(nwbfile, session_path, shankn=shankn,
                                      spikes_nsamples=spikes_nsamples, stub_test=stub_test)
    
        decomp_series = DecompositionSeries(name=metadata_dict['lfp_decomposition']['name'],
                                            description=metadata_dict['lfp_decomposition']['description'],
                                            data=decomp_series_data,
                                            rate=lfp_sampling_rate,
                                            source_timeseries=lfp_ts,
                                            metric='phase', unit='radians') # TODO: should units or metrics be metadata?
        decomp_series.add_band(band_name='theta', band_limits=(4, 10))
        decomp_series.add_band(band_name='gamma', band_limits=(30, 80))
    
        # TODO: check what this really does, and if it can be refactored at all
        check_module(nwbfile, 'ecephys', 'contains processed extracellular electrophysiology data').add_data_interface(decomp_series)
    
        [nwbfile.add_stimulus(x) for x in get_events(session_path)]
    
        # create epochs corresponding to experiments/environments for the mouse
        
        sleep_state_fpath = os.path.join(session_path, '{}--StatePeriod.mat'.format(session_id))
        
        exist_pos_data = any(os.path.isfile(os.path.join(session_path, '{}__{}.mat'.format(session_id, task_type['name'])))
                             for task_type in task_types)
        
        if exist_pos_data:
            nwbfile.add_epoch_column('label', 'name of epoch')
            
        for task_type in task_types:
            label = task_type['name']
    
            file = os.path.join(session_path, session_id + '__' + label + '.mat')
            if os.path.isfile(file):
                pos_obj = Position(name=label + '_position')
    
                matin = loadmat(file)
                tt = matin['twhl_norm'][:, 0]
                exp_times = find_discontinuities(tt)
    
                if 'conversion' in task_type:
                    conversion = task_type['conversion']
                else:
                    conversion = np.nan
    
                for pos_type in ('twhl_norm', 'twhl_linearized'):
                    if pos_type in matin:
                        pos_data_norm = matin[pos_type][:, 1:]
    
                        spatial_series_object = SpatialSeries(
                            name=label + '_{}_spatial_series'.format(pos_type),
                            data=H5DataIO(pos_data_norm, compression='gzip'),
                            reference_frame='unknown', conversion=conversion,
                            resolution=np.nan,
                            #conversion=np.nan,
                            timestamps=H5DataIO(tt, compression='gzip'))
                        pos_obj.add_spatial_series(spatial_series_object)
    
                check_module(nwbfile, 'behavior', 'contains processed behavioral data').add_data_interface(pos_obj)
                for i, window in enumerate(exp_times):
                    nwbfile.add_epoch(start_time=window[0], stop_time=window[1],
                                      label=label + '_' + str(i))
    
        # there are occasional mismatches between the matlab struct and the neuroscope files
        # regions: 3: 'CA3', 4: 'DG'
    
        trialdata_path = os.path.join(session_path, session_id + '__EightMazeRun.mat')
        if os.path.isfile(trialdata_path):
            trials_data = loadmat(trialdata_path)['EightMazeRun']
    
            trialdatainfo_path = os.path.join(fpath_base, 'EightMazeRunInfo.mat')
            trialdatainfo = [x[0] for x in loadmat(trialdatainfo_path)['EightMazeRunInfo'][0]]
    
            features = trialdatainfo[:7]
            features[:2] = 'start_time', 'stop_time',
            [nwbfile.add_trial_column(x, 'description') for x in features[4:] + ['condition']]
    
            for trial_data in trials_data:
                if trial_data[3]:
                    cond = 'run_left'
                else:
                    cond = 'run_right'
                nwbfile.add_trial(start_time=trial_data[0], stop_time=trial_data[1], condition=cond,
                                  error_run=trial_data[4], stim_run=trial_data[5], both_visit=trial_data[6])
        # """
        # mono_syn_fpath = os.path.join(session_path, session_id+'-MonoSynConvClick.mat')
    
        # matin = loadmat(mono_syn_fpath)
        # exc = matin['FinalExcMonoSynID']
        # inh = matin['FinalInhMonoSynID']
    
        # #exc_obj = CatCellInfo(name='excitatory_connections',
        # #                      indices_values=[], cell_index=exc[:, 0] - 1, indices=exc[:, 1] - 1)
        # #module_cellular.add_container(exc_obj)
        # #inh_obj = CatCellInfo(name='inhibitory_connections',
        # #                      indices_values=[], cell_index=inh[:, 0] - 1, indices=inh[:, 1] - 1)
        # #module_cellular.add_container(inh_obj)
        # """
    
        if os.path.isfile(sleep_state_fpath):
            matin = loadmat(sleep_state_fpath)['StatePeriod']
    
            table = TimeIntervals(name='states', description='sleep states of animal')
            table.add_column(name='label', description='sleep state')
    
            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append({'start_time': row[0], 'stop_time': row[1], 'label': name})
            [table.add_row(**row) for row in sorted(data, key=lambda x: x['start_time'])]
    
            check_module(nwbfile, 'behavior', 'contains behavioral data').add_data_interface(table)
        

            
            
            