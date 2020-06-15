from __future__ import print_function

import os
import sys
from datetime import datetime

from hdmf.backends.hdf5.h5_utils import H5DataIO

import numpy as np
import pandas as pd
from dateutil.parser import parse as dateparse
from ephys_analysis.band_analysis import filter_lfp, hilbert_lfp
from pynwb import NWBFile, NWBHDF5IO, TimeSeries
from pynwb.behavior import SpatialSeries, Position
from pynwb.file import Subject, TimeIntervals
from pynwb.misc import DecompositionSeries
from scipy.io import loadmat
from ..utils import check_module

import to_nwb.neuroscope as ns
from to_nwb.utils import find_discontinuities


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

max_shanks = 8


def get_UnitFeatureCell_features(fpath_base, session_id, session_path, max_shanks=max_shanks):
    """Load features from matlab file. Handle occasional mismatches

    Parameters
    ----------
    fpath_base: str
    session_id: str
    session_path: str
    max_shanks: int

    Returns
    -------
    list

    """

    cols_to_get = ('fineCellType', 'region', 'unitID', 'unitIDshank', 'shank')
    matin = loadmat(os.path.join(fpath_base, 'DG_all_6__UnitFeatureSummary_add.mat'),
                    struct_as_record=False)['UnitFeatureCell'][0][0]

    nshanks = min((max_shanks, len(ns.get_shank_channels(session_path))))
    all_ids = []
    all_shanks = []
    for shankn in range(1, nshanks + 1):
        ids = np.unique(ns.read_spike_clustering(session_path, shankn))
        ids = ids[~np.isin(ids, (0, 1))]
        all_ids.append(ids)
        all_shanks.append(np.ones(len(ids), dtype=int) * shankn)
    np.hstack(all_ids)
    np.hstack(all_shanks)
    clu_df = pd.DataFrame(
        {'unitIDshank': np.hstack(all_ids), 'shank': np.hstack(all_shanks)})

    this_file = matin.fname == session_id
    mat_df = pd.DataFrame({col: getattr(matin, col)[this_file].ravel() for col in cols_to_get})

    return pd.merge(clu_df, mat_df, how='left', on=('unitIDshank', 'shank'))


# value taken from Yuta's spreadsheet
special_electrode_dict = {'ch_wait': 79, 'ch_arm': 78, 'ch_solL': 76,
                          'ch_solR': 77, 'ch_dig1': 65, 'ch_dig2': 68,
                          'ch_entL': 72, 'ch_entR': 71, 'ch_SsolL': 73,
                          'ch_SsolR': 70}

# conversion values taken from methods of Senzai, Buzsaki 2017
task_types = [
    {'name': 'OpenFieldPosition_ExtraLarge'},
    {'name': 'OpenFieldPosition_New_Curtain', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_New', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_Old_Curtain', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_Old', 'conversion': 0.46},
    {'name': 'OpenFieldPosition_Oldlast', 'conversion': 0.46},
    {'name': 'EightMazePosition', 'conversion': 0.65 / 2}
]


def get_reference_elec(exp_sheet_path, hilus_csv_path, date, session_id, b=False):
    df = pd.read_csv(hilus_csv_path)
    if session_id in df['session name'].values:
        return df[df['session name'] == session_id]['hilus Ch'].values[0]

    if b:
        date = date.strftime("%-m/%-d/%Y") + 'b'
    try:
        try:
            df1 = pd.read_excel(exp_sheet_path, header=1, sheet_name=1)
            take = df1['implanted'].values == date
            df2 = pd.read_excel(exp_sheet_path, header=3, sheet_name=1)
            out = df2['h'][take[2:]].values[0]
        except:
            df1 = pd.read_excel(exp_sheet_path, header=0, sheet_name=1)
            take = df1['implanted'].values == date
            df2 = pd.read_excel(exp_sheet_path, header=2, sheet_name=1)
            out = df2['h'][take[2:]].values[0]
    except:
        print('no channel found in ' + exp_sheet_path)
        return

    #  handle e.g. '7(52below m)'
    if isinstance(out, str):
        digit_stop = np.where([not x.isdigit() for x in out])[0][0]
        if digit_stop:
            return int(out[:digit_stop])
        else:
            print('invalid channel for ' + exp_sheet_path + ' ' + str(date) + ': ' + out)
            return

    return out


def get_max_electrodes(nwbfile, session_path, max_shanks=max_shanks):
    elec_ids = []
    nshanks = min((len(ns.get_shank_channels(session_path)), max_shanks))
    for shankn in np.arange(1, nshanks + 1, dtype=int):
        df = ns.get_clusters_single_shank(session_path, shankn)
        electrode_group = nwbfile.electrode_groups['shank' + str(shankn)]
        # as a temporary solution, take first channel from shank as max channel
        elec_idx = np.argmax(np.array(nwbfile.electrodes['group']) == electrode_group)
        for i in range(len(set(df['id']))):
            elec_ids.append(elec_idx)
    return elec_ids


def parse_states(fpath):

    state_map = {'H': 'Home', 'M': 'Maze', 'St': 'LDstim',
                 'O': 'Old open field', 'Oc': 'Old open field w/ curtain',
                 'N': 'New open field', 'Ns': 'New open field w/ LDstim',
                 '5hS': '5 hrs of 1 sec every 5 sec', 'L': 'Large open field',
                 'X': 'Extra large open field',
                 'Nc': 'New open field w/ curtain'}

    subject_path, fname = os.path.split(fpath)
    fpath_base, fname = os.path.split(subject_path)
    subject_id, date_text = fname.split('-')
    session_date = dateparse(date_text, yearfirst=True)
    mouse_num = ''.join(filter(str.isdigit, subject_id))
    exp_sheet_path = os.path.join(subject_path, 'YM' + mouse_num + ' exp_sheet.xlsx')
    df = pd.read_excel(exp_sheet_path, sheet_name=1)
    state_ids = df[df['implanted'] == session_date].values[0, 2:15]

    statepath = os.path.join(fpath, 'EEGlength')
    state_times = pd.read_csv(statepath).values
    states = [state_map[x] for x, _ in zip(state_ids, state_times)]

    return states, state_times


def yuta2nwb(session_path='/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/YutaMouse41/YutaMouse41-150903',
             subject_xls=None, include_spike_waveforms=True, stub=True, cache_spec=True):

    subject_path, session_id = os.path.split(session_path)
    fpath_base = os.path.split(subject_path)[0]
    identifier = session_id
    mouse_number = session_id[9:11]
    if '-' in session_id:
        subject_id, date_text = session_id.split('-')
        b = False
    else:
        subject_id, date_text = session_id.split('b')
        b = True

    if subject_xls is None:
        subject_xls = os.path.join(subject_path, 'YM' + mouse_number + ' exp_sheet.xlsx')
    else:
        if not subject_xls[-4:] == 'xlsx':
            subject_xls = os.path.join(subject_xls, 'YM' + mouse_number + ' exp_sheet.xlsx')

    session_start_time = dateparse(date_text, yearfirst=True)

    df = pd.read_excel(subject_xls)

    subject_data = {}
    for key in ['genotype', 'DOB', 'implantation', 'Probe', 'Surgery', 'virus injection', 'mouseID']:
        names = df.iloc[:, 0]
        if key in names.values:
            subject_data[key] = df.iloc[np.argmax(names == key), 1]

    if isinstance(subject_data['DOB'], datetime):
        age = session_start_time - subject_data['DOB']
    else:
        age = None

    subject = Subject(subject_id=subject_id, age=str(age),
                      genotype=subject_data['genotype'],
                      species='mouse')

    nwbfile = NWBFile(session_description='mouse in open exploration and theta maze',
                      identifier=identifier,
                      session_start_time=session_start_time.astimezone(),
                      file_create_date=datetime.now().astimezone(),
                      experimenter='Yuta Senzai',
                      session_id=session_id,
                      institution='NYU',
                      lab='Buzsaki',
                      subject=subject,
                      related_publications='DOI:10.1016/j.neuron.2016.12.011')

    print('reading and writing raw position data...', end='', flush=True)
    ns.add_position_data(nwbfile, session_path)

    shank_channels = ns.get_shank_channels(session_path)[:8]
    all_shank_channels = np.concatenate(shank_channels)

    print('setting up electrodes...', end='', flush=True)
    hilus_csv_path = os.path.join(fpath_base, 'early_session_hilus_chans.csv')
    lfp_channel = get_reference_elec(subject_xls, hilus_csv_path, session_start_time, session_id, b=b)
    print(lfp_channel)
    custom_column = [{'name': 'theta_reference',
                      'description': 'this electrode was used to calculate LFP canonical bands',
                      'data': all_shank_channels == lfp_channel}]
    ns.write_electrode_table(nwbfile, session_path, custom_columns=custom_column, max_shanks=max_shanks)

    print('reading LFPs...', end='', flush=True)
    lfp_fs, all_channels_data = ns.read_lfp(session_path, stub=stub)

    lfp_data = all_channels_data[:, all_shank_channels]
    print('writing LFPs...', flush=True)
    # lfp_data[:int(len(lfp_data)/4)]
    lfp_ts = ns.write_lfp(nwbfile, lfp_data, lfp_fs, name='lfp',
                          description='lfp signal for all shank electrodes')

    for name, channel in special_electrode_dict.items():
        ts = TimeSeries(name=name, description='environmental electrode recorded inline with neural data',
                        data=all_channels_data[:, channel], rate=lfp_fs, unit='V', conversion=np.nan, resolution=np.nan)
        nwbfile.add_acquisition(ts)

    # compute filtered LFP
    print('filtering LFP...', end='', flush=True)
    all_lfp_phases = []
    for passband in ('theta', 'gamma'):
        lfp_fft = filter_lfp(lfp_data[:, all_shank_channels == lfp_channel].ravel(), lfp_fs, passband=passband)
        lfp_phase, _ = hilbert_lfp(lfp_fft)
        all_lfp_phases.append(lfp_phase[:, np.newaxis])
    data = np.dstack(all_lfp_phases)
    print('done.', flush=True)

    if include_spike_waveforms:
        print('writing waveforms...', end='', flush=True)
        nshanks = min((max_shanks, len(ns.get_shank_channels(session_path))))
        for shankn in np.arange(nshanks, dtype=int) + 1:
            ns.write_spike_waveforms(nwbfile, session_path, shankn, stub=stub)
        print('done.', flush=True)

    decomp_series = DecompositionSeries(name='LFPDecompositionSeries',
                                        description='Theta and Gamma phase for reference LFP',
                                        data=data, rate=lfp_fs,
                                        source_timeseries=lfp_ts,
                                        metric='phase', unit='radians')
    decomp_series.add_band(band_name='theta', band_limits=(4, 10))
    decomp_series.add_band(band_name='gamma', band_limits=(30, 80))

    check_module(nwbfile, 'ecephys', 'contains processed extracellular electrophysiology data').add_data_interface(decomp_series)

    [nwbfile.add_stimulus(x) for x in ns.get_events(session_path)]

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
            print('loading position for ' + label + '...', end='', flush=True)

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
                        timestamps=H5DataIO(tt, compression='gzip'))
                    pos_obj.add_spatial_series(spatial_series_object)

            check_module(nwbfile, 'behavior', 'contains processed behavioral data').add_data_interface(pos_obj)
            for i, window in enumerate(exp_times):
                nwbfile.add_epoch(start_time=window[0], stop_time=window[1],
                                  label=label + '_' + str(i))
            print('done.')

    # there are occasional mismatches between the matlab struct and the neuroscope files
    # regions: 3: 'CA3', 4: 'DG'

    df_unit_features = get_UnitFeatureCell_features(fpath_base, session_id, session_path)

    celltype_names = []
    for celltype_id, region_id in zip(df_unit_features['fineCellType'].values,
                                      df_unit_features['region'].values):
        if celltype_id == 1:
            if region_id == 3:
                celltype_names.append('pyramidal cell')
            elif region_id == 4:
                celltype_names.append('granule cell')
            else:
                raise Exception('unknown type')
        elif not np.isfinite(celltype_id):
            celltype_names.append('missing')
        else:
            celltype_names.append(celltype_dict[celltype_id])

    custom_unit_columns = [
        {
            'name': 'cell_type',
            'description': 'name of cell type',
            'data': celltype_names},
        {
            'name': 'global_id',
            'description': 'global id for cell for entire experiment',
            'data': df_unit_features['unitID'].values},
        {
            'name': 'max_electrode',
            'description': 'electrode that has the maximum amplitude of the waveform',
            'data': get_max_electrodes(nwbfile, session_path),
            'table': nwbfile.electrodes
        }]

    ns.add_units(nwbfile, session_path, custom_unit_columns, max_shanks=max_shanks)

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

    if stub:
        out_fname = session_path + '_stub.nwb'
    else:
        out_fname = session_path + '.nwb'

    print('writing NWB file...', end='', flush=True)
    with NWBHDF5IO(out_fname, mode='w') as io:
        io.write(nwbfile, cache_spec=cache_spec)
    print('done.')

    print('testing read...', end='', flush=True)
    # test read
    with NWBHDF5IO(out_fname, mode='r') as io:
        io.read()
    print('done.')


def main(argv):
    yuta2nwb()


if __name__ == "__main__":
    main(sys.argv[1:])
