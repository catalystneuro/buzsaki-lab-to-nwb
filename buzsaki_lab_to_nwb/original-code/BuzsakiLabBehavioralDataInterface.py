
from copy import deepcopy
from nwb_conversion_tools.utils import get_base_schema, get_schema_from_hdmf_class
from nwb_conversion_tools.BaseDataInterface import BaseDataInterface
from pynwb.behavior import SpatialSeries,Position
import numpy as np
from pynwb import NWBFile, TimeSeries
from pathlib import Path
from typing import Union
import os
import pandas as pd
from hdmf.backends.hdf5.h5_utils import H5DataIO
from bs4 import BeautifulSoup
from hdmf.data_utils import DataChunkIterator
from tqdm import tqdm
from glob import glob
from pynwb.ecephys import ElectricalSeries, LFP, SpikeEventSeries

# TODO: there doesn't seem to be a pypi for ephys_analysis... copy entire library here or just these functions?
from ephys_analysis.band_analysis import filter_lfp, hilbert_lfp

from pynwb.misc import DecompositionSeries, AnnotationSeries
from scipy.io import loadmat
from pynwb.file import TimeIntervals

PathType = Union[str, Path, None]


def add_position_data(nwbfile, session_path, names, fs):
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
    session_name = os.path.split(session_path)[1]
    whl_path = os.path.join(session_path, session_name + '.whl')
    if not os.path.isfile(whl_path):
        print('Warning: File not found (' + whl_path + ')!')
        return
    df = pd.read_csv(whl_path, sep='\t', names=names)

    nwbfile.add_acquisition(
        SpatialSeries('position_sensor0',
                      H5DataIO(df[[names[0], names[1]]].values, compression='gzip'),
                      'unknown', description='raw sensor data from sensor 0',
                      rate = fs,
                      starting_time = 0.,
                      resolution=np.nan))

    nwbfile.add_acquisition(
        SpatialSeries('position_sensor1',
                      H5DataIO(df[[names[2], names[3]]].values, compression='gzip'),
                      'unknown', description='raw sensor data from sensor 1',
                      rate = fs,
                      starting_time = 0.,
                      resolution=np.nan))
    
    
def load_xml(filepath):
    with open(filepath, 'r') as xml_file:
        contents = xml_file.read()
        soup = BeautifulSoup(contents, 'xml')
    return soup

    
def get_lfp_sampling_rate(session_path=None, xml_filepath=None):
    """Reads the LFP Sampling Rate from the xml parameter file of the
    Neuroscope format

    Parameters
    ----------
    session_path: str
    xml_filepath: None | str (optional)

    Returns
    -------
    fs: float

    """

    if xml_filepath is None:
        session_name = os.path.split(session_path)[1]
        xml_filepath = os.path.join(session_path, session_name + '.xml')

    return float(load_xml(xml_filepath).lfpSamplingRate.string)

def get_n_channels(session_path=None, xml_filepath=None):
    """Reads the number of channels from the xml parameter file of the
    Neuroscope format

    Parameters
    ----------
    session_path: str
    xml_filepath: None | str (optional)

    Returns
    -------
    fs: int

    """

    if xml_filepath is None:
        session_name = os.path.split(session_path)[1]
        xml_filepath = os.path.join(session_path, session_name + '.xml')

    return int(load_xml(xml_filepath).nChannels.string)



def get_bit_type(session_path=None, xml_filepath=None):
    """Reads the bit type usued to record data from the xml parameter file of the
    Neuroscope format

    Parameters
    ----------
    session_path: str
    xml_filepath: None | str (optional)

    Returns
    -------
    fs: int

    """

    if xml_filepath is None:
        session_name = os.path.split(session_path)[1]
        xml_filepath = os.path.join(session_path, session_name + '.xml')

    return int(load_xml(xml_filepath).nBits.string)

    
def read_lfp(session_path: PathType, stub_test: bool = False):
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
    lfp_fs = get_lfp_sampling_rate(session_path)
    n_channels = get_n_channels(session_path)
    bit_type = get_bit_type(session_path)

    fpath_base, fname = os.path.split(session_path)
    lfp_filepath = os.path.join(session_path, fname + '.eeg')
    
    if stub_test:
        max_size = 50
        all_channels_data = np.fromfile(lfp_filepath,
                                        dtype='int'+str(bit_type),
                                        count = max_size*n_channels).reshape(-1, n_channels)
    else:
        all_channels_data = np.fromfile(lfp_filepath,
                                        dtype='int'+str(bit_type)).reshape(-1, n_channels)

    return lfp_fs, all_channels_data


def check_module(nwbfile, name, description=None):
    """Check if processing module exists. If not, create it. Then return module
    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    name: str
    description: str | None (optional)
    Returns
    -------
    pynwb.module
    """

    if name in nwbfile.modules:
        return nwbfile.modules[name]
    else:
        if description is None:
            description = name
        return nwbfile.create_processing_module(name, description)


def write_lfp(nwbfile, data, fs, name='LFP', description='local field potential signal', electrode_inds=None):
    """
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

    """

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
    """
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

    """
    _, session_name = os.path.split(session_path)
    timing_file = os.path.join(session_path, session_name + '.res.' + str(shankn))
    timing_df = pd.read_csv(timing_file, names=('time',))

    return timing_df.values.ravel() / fs


def write_spike_waveforms(nwbfile: NWBFile, session_path: PathType, shankn: int,
                          stub_test: bool = False, compression: str = 'gzip'):
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
    xml_filepath = os.path.join(session_path, session_name + '.xml')
    spk_file = os.path.join(session_path, session_name + '.spk.' + str(shankn))
    if not os.path.isfile(spk_file):
            print('Warning: Spike waveforms for shank{} not found!'.format(shankn))
            return

    group = nwbfile.electrode_groups['shank' + str(shankn)]
    elec_idx = list(np.where(np.array(nwbfile.ec_electrodes['group']) == group)[0])
    table_region = nwbfile.create_electrode_table_region(elec_idx, group.name + ' region')

    nchan = len(elec_idx)
    soup = load_xml(xml_filepath)
    nsamps = int(soup.spikes.nSamples.string)

    if stub_test:
        max_size = 50
        spks = np.fromfile(spk_file,
                           dtype=np.int16,
                           count=max_size*nsamps*nchan).reshape(-1, nsamps, nchan)
        spike_times = read_spike_times(session_path, shankn).reshape(spks.size)
    else:
        spks = np.fromfile(spk_file,
                           dtype=np.int16).reshape(-1, nsamps, nchan)
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
    """
    Parameters
    ----------
    session_path: str
    suffixes: Iterable(str), optional
        The 3-letter names for the events to write. If None, detect all in session_path

    """
    session_name = os.path.split(session_path)[1]

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
        
        return metadata_schema # RecordingExtractor metadata json-schema here.
    
    
    def get_metadata(self, session_path: PathType, metadata: dict = None):
        pass
    
    
    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict,
                     stub_test: bool = False, include_spike_waveforms: bool = False):
        # TODO: generalize this and check/enforce format
        all_shank_channels = metadata_dict['shank_channels']
        special_electrode_dict = metadata_dict['special_electrode_dict']
        lfp_channel = metadata_dict['lfp_channel']
        nshanks = metadata_dict['nshanks']
        task_types = metadata_dict['task_types']
        
        # TODO: temporary
        fs = 1250 / 32
        names=('x0', 'y0', 'x1', 'y1')
        session_path = "D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903"
        subject_path, session_id = os.path.split(session_path)
        fpath_base = os.path.split(subject_path)[0]
        
        add_position_data(nwbfile, session_path, names, fs)
        lfp_fs, all_channels_lfp_data = read_lfp(session_path, stub_test=stub_test)
        lfp_data = all_channels_lfp_data[:, all_shank_channels]
        lfp_ts = write_lfp(nwbfile, lfp_data, lfp_fs, name='lfp',
                              description='lfp signal for all shank electrodes')
    
        for name, channel in special_electrode_dict.items():
            ts = TimeSeries(name=name,
                            description='environmental electrode recorded inline with neural data',
                            data=all_channels_lfp_data[:, channel], rate=lfp_fs, unit='V',
                            #conversion=np.nan, 
                            resolution=np.nan)
            nwbfile.add_acquisition(ts)
    
        all_lfp_phases = []
        for passband in ('theta', 'gamma'):
            lfp_fft = filter_lfp(lfp_data[:, all_shank_channels == lfp_channel].ravel(), lfp_fs, passband=passband)
            lfp_phase, _ = hilbert_lfp(lfp_fft)
            all_lfp_phases.append(lfp_phase[:, np.newaxis])
        data = np.dstack(all_lfp_phases)
    
        if include_spike_waveforms:
            for shankn in np.arange(nshanks, dtype=int) + 1:
                write_spike_waveforms(nwbfile, session_path, shankn, stub_test=stub_test)
    
        decomp_series = DecompositionSeries(name='LFPDecompositionSeries',
                                            description='Theta and Gamma phase for reference LFP',
                                            data=data, rate=lfp_fs,
                                            source_timeseries=lfp_ts,
                                            metric='phase', unit='radians')
        decomp_series.add_band(band_name='theta', band_limits=(4, 10))
        decomp_series.add_band(band_name='gamma', band_limits=(30, 80))
    
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
        """
        mono_syn_fpath = os.path.join(session_path, session_id+'-MonoSynConvClick.mat')
    
        matin = loadmat(mono_syn_fpath)
        exc = matin['FinalExcMonoSynID']
        inh = matin['FinalInhMonoSynID']
    
        #exc_obj = CatCellInfo(name='excitatory_connections',
        #                      indices_values=[], cell_index=exc[:, 0] - 1, indices=exc[:, 1] - 1)
        #module_cellular.add_container(exc_obj)
        #inh_obj = CatCellInfo(name='inhibitory_connections',
        #                      indices_values=[], cell_index=inh[:, 0] - 1, indices=inh[:, 1] - 1)
        #module_cellular.add_container(inh_obj)
        """
    
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
        

            
            
            