"""
Author: Ben Dichter
"""
import os
from glob import glob

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from pynwb.behavior import SpatialSeries
from pynwb.ecephys import ElectricalSeries, LFP, SpikeEventSeries, EventWaveform#, UnitSeries
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator
from pynwb.misc import AnnotationSeries
from tqdm import tqdm

from .utils import check_module


def load_xml(filepath):
    with open(filepath, 'r') as xml_file:
        contents = xml_file.read()
        soup = BeautifulSoup(contents, 'xml')
    return soup


def get_channel_groups(session_path=None, xml_filepath=None):
    """Get the groups of channels that are recorded on each shank from the xml
    file

    Parameters
    ----------
    session_path: str
    xml_filepath: None | str (optional)

    Returns
    -------
    list(list)

    """
    if xml_filepath is None:
        fpath_base, fname = os.path.split(session_path)
        xml_filepath = os.path.join(session_path, fname + '.xml')

    soup = load_xml(xml_filepath)

    channel_groups = [[int(channel.string)
                       for channel in group.find_all('channel')]
                      for group in soup.channelGroups.find_all('group')]

    return channel_groups


def get_shank_channels(session_path=None, xml_filepath=None):
    """Read the channels on the shanks in Neuroscope xml

    Parameters
    ----------
    session_path: str
    xml_filepath: None | str (optional)

    Returns
    -------
    list(list(int))

    """
    if xml_filepath is None:
        fpath_base, fname = os.path.split(session_path)
        xml_filepath = os.path.join(session_path, fname + '.xml')

    soup = load_xml(xml_filepath)

    shank_channels = [[int(channel.string)
                       for channel in group.find_all('channel')]
                      for group in soup.spikeDetection.channelGroups.find_all('group')]
    return shank_channels


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


def add_position_data(nwbfile, session_path, fs=1250./32.,
                      names=('x0', 'y0', 'x1', 'y1')):
    """Read raw position sensor data from .whl file

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str
    fs: float
        sampling rate
    names: iterable
        names of column headings

    """
    session_name = os.path.split(session_path)[1]
    whl_path = os.path.join(session_path, session_name + '.whl')
    if not os.path.isfile(whl_path):
        print(whl_path + ' file not found!')
        return
    print('warning: time may not be aligned')
    df = pd.read_csv(whl_path, sep='\t', names=names)

    df.index = np.arange(len(df)) / fs
    df.index.name = 'tt (sec)'

    nwbfile.add_acquisition(
        SpatialSeries('position_sensor0',
                      H5DataIO(df[['x0', 'y0']].values, compression='gzip'),
                      'unknown', description='raw sensor data from sensor 0',
                      timestamps=H5DataIO(df.index.values, compression='gzip'),
                      resolution=np.nan))

    nwbfile.add_acquisition(
        SpatialSeries('position_sensor1',
                      H5DataIO(df[['x1', 'y1']].values, compression='gzip'),
                      'unknown', description='raw sensor data from sensor 1',
                      timestamps=H5DataIO(df.index.values, compression='gzip'),
                      resolution=np.nan))


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


def read_spike_clustering(session_path, shankn):
    """
    Read .clu files to get spike cluster assignments for a single shank

    Parameters
    ----------
    session_path: str | path
    shankn: int
        shank number (1-indexed)

    Returns
    -------
    np.ndarray


    """
    session_name = os.path.split(session_path)[1]
    id_file = os.path.join(session_path, session_name + '.clu.' + str(shankn))
    id_df = pd.read_csv(id_file, names=('id',))
    id_df = id_df[1:]  # the first number is the number of clusters

    return id_df.values.ravel()


def get_clusters_single_shank(session_path, shankn, fs=20000.):
    """Read the spike time data for a from the .res and .clu files for a single
    shank. Automatically removes noise and multi-unit.

    Parameters
    ----------
    session_path: str | path
        session path
    shankn: int
        shank number (1-indexed)
    fs: float

    Returns
    -------
    df: pd.DataFrame
        has column named 'id' which indicates cluster id and 'time' which
        indicates spike time.

    """

    spike_times = read_spike_times(session_path, shankn, fs=fs)
    spike_ids = read_spike_clustering(session_path, shankn)
    df = pd.DataFrame({'id': spike_ids, 'time': spike_times})
    noise_inds = ((df.iloc[:, 0] == 0) | (df.iloc[:, 0] == 1)).values.ravel()
    df = df.loc[np.logical_not(noise_inds)].reset_index(drop=True)

    df['id'] -= 2

    return df


def write_unit_series(nwbfile, session_path, shankn, fs=20000.):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str | path
    shankn: int
        shank number (1-indexed)
    fs: float

    """
    """
    # find first row where units are from this shank
    start = np.argmax(nwbfile.units.electrode_group == nwbfile.electrode_groups['shank' + str(shankn)])

    df = get_clusters_single_shank(session_path, shankn, fs=fs)

    # TO DO: link timestamps to SpikeEventSeries
    
    unit_series = UnitSeries(
        name='UnitSeries' + str(shankn),
        description='shank' + str(shankn),
        num=df['id'].values + start,
        timestamps=df['time'].values)
    

    ecephys_module = check_module(nwbfile, 'ecephys')
    if 'SpikeEventSeries' + str(shankn) in ecephys_module:
        ecephys_module['SpikeEventSeries' + str(shankn)].unit_series = unit_series
    else:
        print('UnitSeries' + str(shankn) + ' not linked with a SpikeEventSeries object')

    ecephys_module.add_data_interface(unit_series)
    """


def write_electrode_table(nwbfile, session_path, electrode_positions=None,
                          impedances=None, locations=None, filterings=None, custom_columns=(),
                          max_shanks=None):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str
    electrode_positions: Iterable(Iterable(float))
    impedances: array-like(dtype=float) (optional)
    locations: array-like(dtype=str) (optional)
    filterings: array-like(dtype=str) (optional)
    custom_columns: list(dict) (optional)
        {name, description, data} for any custom columns
    max_shanks: int | None

    """
    fpath_base, fname = os.path.split(session_path)

    shank_channels = get_shank_channels(session_path)
    if max_shanks:
        shank_channels = shank_channels[:max_shanks]
    nwbfile.add_electrode_column('shank_electrode_number', '1-indexed channel within a shank')
    nwbfile.add_electrode_column('amp_channel', 'order in which the channels were plugged into amp')
    for custom_column in custom_columns:
        nwbfile.add_electrode_column(custom_column['name'],
                                     custom_column['description'])

    device = nwbfile.create_device('implant', fname + '.xml')
    for shankn, channels in enumerate(shank_channels):
        shankn += 1
        electrode_group = nwbfile.create_electrode_group(
            name='shank{}'.format(shankn),
            description='shank{} electrodes'.format(shankn),
            device=device, location='unknown')
        for shank_electrode_number, amp_channel in enumerate(channels):
            if electrode_positions is not None:
                pos = electrode_positions[amp_channel]
            else:
                pos = (np.nan, np.nan, np.nan)

            if impedances is None:
                imp = np.nan
            else:
                imp = impedances[amp_channel]

            if locations is None:
                location = 'unknown'
            else:
                location = locations[amp_channel]

            if filterings is None:
                filtering = 'unknown'
            else:
                filtering = filterings[amp_channel]

            custom_data = {custom_col['name']: custom_col['data'][amp_channel]
                           for custom_col in custom_columns}

            nwbfile.add_electrode(
                float(pos[0]), float(pos[1]), float(pos[2]),
                imp=imp, location=location, filtering=filtering,
                group=electrode_group, amp_channel=amp_channel,
                shank_electrode_number=shank_electrode_number, **custom_data)


def read_lfp(session_path, stub=False):
    """

    Parameters
    ----------
    session_path: str
    stub: bool, optional
        Default is False. If True, don't read LFP, but instead add a small
        amount of placeholder data. This is useful for rapidly checking new
        features without the time-intensive data read step.

    Returns
    -------
    lfp_fs, all_channels_data

    """
    lfp_fs = get_lfp_sampling_rate(session_path)
    n_channels = sum(len(x) for x in get_channel_groups(session_path))
    if stub:
        all_channels_lfp = np.random.randn(1000, n_channels)  # use for dev testing for speed
        return lfp_fs, all_channels_lfp

    fpath_base, fname = os.path.split(session_path)
    lfp_filepath = os.path.join(session_path, fname + '.eeg')

    all_channels_data = np.fromfile(lfp_filepath, dtype=np.int16).reshape(-1, n_channels)

    return lfp_fs, all_channels_data


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
        electrode_inds = list(range(data.shape[1]))

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


def add_lfp(nwbfile, session_path, name='LFP', description='local field potential signal', stub=False):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str
    name: str, optional
    description: str, optional
    stub: bool, optional
        Default is False. If True, don't read LFP, but instead add a small
        amount of placeholder data. This is useful for rapidly checking new
        features without the time-intensive data read step.

    """

    fs, data = read_lfp(session_path, stub=stub)
    shank_channels = get_shank_channels(session_path)
    all_shank_channels = np.concatenate(shank_channels)
    write_lfp(nwbfile, data[:, all_shank_channels], fs, name, description)


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


def write_events(nwbfile, session_path, suffixes=None, module=None):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str
    suffixes: Iterable(str), optional
        The 3-letter names for the events to write. If None, detect all in session_path
    module: pynwb.processing_module

    """
    session_name = os.path.split(session_path)[1]

    if suffixes is None:
        evt_files = glob(os.path.join(session_path, session_name) + '.evt.*') + \
                    glob(os.path.join(session_path, session_name) + '.*.evt')
    else:
        evt_files = [os.path.join(session_path, session_name + s)
                     for s in suffixes]
    if module is None:
        module = check_module(nwbfile, 'events')
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
            annotation_series = AnnotationSeries(
                name=name, data=data, timestamps=timestamps)
            module.add_data_interface(annotation_series)


def write_spike_waveforms(nwbfile, session_path, shankn, stub=False, compression='gzip'):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFiles
    session_path: str
    shankn: int
    stub: bool, optional
        default: False
    compression: str (optional)

    Returns
    -------

    """

    session_name = os.path.split(session_path)[1]
    xml_filepath = os.path.join(session_path, session_name + '.xml')

    group = nwbfile.electrode_groups['shank' + str(shankn)]
    elec_idx = list(np.where(np.array(nwbfile.ec_electrodes['group']) == group)[0])
    table_region = nwbfile.create_electrode_table_region(elec_idx, group.name + ' region')

    nchan = len(elec_idx)
    soup = load_xml(xml_filepath)
    nsamps = int(soup.spikes.nSamples.string)

    if stub:
        spks = np.random.randn(10, nsamps, nchan)
        spike_times = np.arange(10)
    else:
        spk_file = os.path.join(session_path, session_name + '.spk.' + str(shankn))
        if not os.path.isfile(spk_file):
            print('spike waveforms for shank{} not found'.format(shankn))
            return
        spks = np.fromfile(spk_file, dtype=np.int16).reshape(-1, nsamps, nchan)
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


def add_units(nwbfile, session_path, custom_cols=None, max_shanks=8):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    session_path: str
    custom_cols: list(dict), optional
        [{name, description, data, kwargs}]
    max_shanks: int
        only take the first <max_shanks> channel groups

    Returns
    -------

    """

    nwbfile.add_unit_column('shank_id', '0-indexed id of cluster of shank')
    nshanks = len(get_shank_channels(session_path))
    nshanks = min((max_shanks, nshanks))

    for shankn in range(1, nshanks + 1):
        df = get_clusters_single_shank(session_path, shankn)
        electrode_group = nwbfile.electrode_groups['shank' + str(shankn)]
        for shank_id, idf in df.groupby('id'):
            nwbfile.add_unit(spike_times=idf['time'].values, shank_id=shank_id, electrode_group=electrode_group)

    if custom_cols:
        [nwbfile.add_unit_column(**x) for x in custom_cols]

    return nwbfile
