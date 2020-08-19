
from nwb_conversion_tools import NWBConverter, NeuroscopeDataInterface
import pandas as pd
import numpy as np
import os
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.parser import parse as dateparse
from pathlib import Path
from typing import Union
from scipy.io import loadmat
import BuzsakiLabBehavioralDataInterface

PathType = Union[str, Path, None]

def get_shank_channels(session_path = None, xml_filepath = None):
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
        
        with open(xml_filepath, 'r') as xml_file:
            contents = xml_file.read()
            soup = BeautifulSoup(contents, 'xml')
    
        shank_channels = [[int(channel.string)
                           for channel in group.find_all('channel')]
                           for group in soup.spikeDetection.channelGroups.find_all('group')]
        return shank_channels
    
    
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
        print('Warning: no channel found in ' + exp_sheet_path)
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


def get_clusters_single_shank(session_path, shankn, fs=20000.):
    """Read the spike time data from the .res and .clu files for a single
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


def get_max_electrodes(nwbfile, session_path):
    elec_ids = []
    nshanks = len(get_shank_channels(session_path))
    for shankn in np.arange(1, nshanks + 1, dtype=int):
        df = get_clusters_single_shank(session_path, shankn)
        electrode_group = nwbfile.electrode_groups['shank' + str(shankn)]
        # as a temporary solution, take first channel from shank as max channel
        elec_idx = np.argmax(np.array(nwbfile.electrodes['group']) == electrode_group)
        for i in range(len(set(df['id']))):
            elec_ids.append(elec_idx)
    return elec_ids


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


def get_UnitFeatureCell_features(fpath_base, session_id, session_path):
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
    matin = loadmat(os.path.join(fpath_base,'_extra/DG_all_6/DG_all_6__UnitFeatureSummary_add.mat'), # Cody: modified path a bit for my location
                    struct_as_record=False)['UnitFeatureCell'][0][0]

    nshanks = len(get_shank_channels(session_path))
    all_ids = []
    all_shanks = []
    for shankn in range(1, nshanks + 1):
        ids = np.unique(read_spike_clustering(session_path, shankn))
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


class BuzsakiLabNWBConverter(NWBConverter):
    data_interface_classes = {'NeuroscopeRecording': NeuroscopeDataInterface.NeuroscopeRecordingInterface,
                              'NeuroscopeSorting': NeuroscopeDataInterface.NeuroscopeSortingInterface,
                              'BuzsakiLabBehavioral': BuzsakiLabBehavioralDataInterface.BuzsakiLabBehavioralDataInterface}
    
    
    def __init__(self, **input_paths):
        NWBConverter.__init__(self, **input_paths)
    
    
    def get_metadata(self, session_path: PathType, metadata: dict = None):
        
        if metadata is None:
            metadata = {}

        # TODO: could be vastly improved with pathlib
        subject_path, session_id = os.path.split(session_path)
        fpath_base = os.path.split(subject_path)[0]
        mouse_number = session_id[9:11] # TODO: improve
        if '-' in session_id:
            subject_id, date_text = session_id.split('-')
            b = False
        else:
            subject_id, date_text = session_id.split('b')
            b = True
            
        shank_channels = get_shank_channels(session_path)
        
        subject_xls = os.path.join(subject_path, 'YM' + mouse_number + ' exp_sheet.xlsx')
        hilus_csv_path = os.path.join(fpath_base, 'early_session_hilus_chans.csv')
        lfp_channel = get_reference_elec(subject_xls,
                                          hilus_csv_path,
                                          dateparse(date_text, yearfirst = True),
                                          session_id,
                                          b = b)
        shank_electrode_number = [x for _, channels in enumerate(shank_channels) for x, _ in enumerate(channels)]
        
        # Temporarily suppressing max_electrode until the function is verified
        #max_electrodes = get_max_electrodes(nwbfile, session_path)
    
        # Cell types might be Yuta specific? Or general convention for lab?
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
                
        sorting_electrode_groups = []        
        for shankn in range(len(shank_channels)):
            df = get_clusters_single_shank(session_path, shankn+1)
            for shank_id, idf in df.groupby('id'):
                sorting_electrode_groups.append('shank' + str(shankn+1))
                
                
        special_electrode_dict = {'ch_wait': 79, 'ch_arm': 78, 'ch_solL': 76,
                          'ch_solR': 77, 'ch_dig1': 65, 'ch_dig2': 68,
                          'ch_entL': 72, 'ch_entR': 71, 'ch_SsolL': 73,
                          'ch_SsolR': 70}
        
        task_types = [
            {'name': 'OpenFieldPosition_ExtraLarge'},
            {'name': 'OpenFieldPosition_New_Curtain', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_New', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_Old_Curtain', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_Old', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_Oldlast', 'conversion': 0.46},
            {'name': 'EightMazePosition', 'conversion': 0.65 / 2}
        ]
    
        metadata = {
            'NWBFile': {
                'identifier': session_id,
                'session_start_time': (dateparse(date_text, yearfirst = True)).astimezone(),
                'file_create_date': datetime.now().astimezone(),
                'session_id': session_id,
                'institution': 'NYU',
                'lab': 'Buzsaki'
            },
            'Subject': {
                'subject_id': subject_id,
                'age': '346 days',
                'genotype': 'POMC-Cre::Arch',
                'species': 'mouse' # should be Mus musculus?
            },
            'NeuroscopeRecording': {
                'Ecephys': {
                    # NwbRecordingExtractor expects metadata to be lists of dictionaries
                    'Device': [{
                        'description': session_id + '.xml'
                    }],
                    'ElectrodeGroup': [{
                        'name': f'shank{n+1}',
                        'description': f'shank{n+1} electrodes'
                    } for n, _ in enumerate(shank_channels)],
                    'Electrodes': [
                        {
                            'name': 'theta_reference',
                            'description': 'this electrode was used to calculate LFP canonical bands',
                            'data':  list(np.concatenate(shank_channels) == lfp_channel)
                        },
                        {
                            'name': 'shank_electrode_number',
                            'description': '1-indexed channel within a shank',
                            'data': shank_electrode_number
                        },
                        {
                            'name': 'amp_channel',
                            'description': 'order in which the channels were plugged into amp',
                            'data': [x for _, channels in enumerate(shank_channels) for _, x in enumerate(channels)]
                        }
                    ],
                    'ElectricalSeries': [{
                        'name': 'ElectricalSeries',
                        'description': 'raw acquisition traces'
                    }]
                }
            },
            'NeuroscopeSorting': {
                'UnitProperties': [
                    {
                        'name': 'cell_type',
                        'description': 'name of cell type',
                        'data': celltype_names
                    },
                    {
                        'name': 'global_id',
                        'description': 'global id for cell for entire experiment',
                        'data': df_unit_features['unitID'].values
                    },
                    {
                        'name': 'shank_id',
                        'description': '0-indexed id of cluster of shank',
                        # - 2 b/c the get_UnitFeatureCell_features removes 0 and 1 IDs from each shank
                        'data': [x - 2 for x in df_unit_features['unitIDshank'].values]
                    },
                    {
                        'name': 'electrode_group',
                        'description': 'the electrode group that each spike unit came from',
                        'data': sorting_electrode_groups
                            # ['shank' + str(n+1) for n, shank_channel in 
                                     # enumerate(shank_channels) for _ in shank_channel]
                    }
                    # Temporarily suppressing max_electrode until the function is verified
                    #,
                    # {
                    #     'name': 'max_electrode',
                    #     'description': 'electrode that has the maximum amplitude of the waveform',
                    #     'data': max_electrodes
                    # }
                  ]
            },
            'BuzsakiLabBehavioral': {
                'shank_channels': np.concatenate(shank_channels),
                'special_electrode_dict': special_electrode_dict,
                'lfp_channel': lfp_channel,
                'nshanks': len(shank_channels),
                'task_types': task_types
            }
        }
            
        return metadata
