"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools import NWBConverter, neuroscopedatainterface
import yutapositiondatainterface
import yutalfpdatainterface
import yutabehaviordatainterface
import yutanorecording
import pandas as pd
import numpy as np
from scipy.io import loadmat
import os
from lxml import etree as et
from datetime import datetime
from dateutil.parser import parse as dateparse
from pathlib import Path
from typing import Union
from to_nwb.neuroscope import get_clusters_single_shank, read_spike_clustering

PathType = Union[str, Path, None]


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


def get_UnitFeatureCell_features(fpath_base, session_id, session_path, nshanks):
    """Load features from matlab file. Handle occasional mismatches.

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
    # TODO: add file existence checks
    cols_to_get = ('fineCellType', 'region', 'unitID', 'unitIDshank', 'shank')
    matin = loadmat(os.path.join(fpath_base, '_extra/DG_all_6/DG_all_6__UnitFeatureSummary_add.mat'),
                    struct_as_record=False)['UnitFeatureCell'][0][0]

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


class YutaNWBConverter(NWBConverter):
    # The order of this dictionary matter significantly, but python dictionaries are supposed to be unordered
    # This is compensated for the time being, but should this conceptually be a list instead?
    data_interface_classes = {'NeuroscopeRecording': neuroscopedatainterface.NeuroscopeRecordingInterface,
                              'NeuroscopeSorting': neuroscopedatainterface.NeuroscopeSortingInterface,
                              'YutaPosition': yutapositiondatainterface.YutaPositionInterface,
                              'YutaLFP': yutalfpdatainterface.YutaLFPInterface,
                              'YutaBehavior': yutabehaviordatainterface.YutaBehaviorInterface}

    def __init__(self, **input_args):
        dat_filepath = input_args.get('NeuroscopeRecording', {}).get('file_path', None)
        if not os.path.isfile(dat_filepath):
            new_data_interface_classes = {}
            
            new_data_interface_classes.update({'YutaNoRecording': yutanorecording.YutaNoRecording})
            for name, val in self.data_interface_classes.items():
                new_data_interface_classes.update({name: val})
            new_data_interface_classes.pop('NeuroscopeRecording')

            session_id = os.path.split(input_args['NeuroscopeSorting']['folder_path'])[1]
            xml_filepath = os.path.join(input_args['NeuroscopeSorting']['folder_path'], session_id + '.xml')
            root = et.parse(xml_filepath).getroot()
            n_channels = len([[int(channel.text)
                              for channel in group.find('channels')]
                              for group in root.find('spikeDetection').find('channelGroups').findall('group')])
            # The only information needed for this is .get_channel_ids() which is set by the shape of the input series
            input_args.update({'YutaNoRecording': {'timeseries': np.array(range(n_channels)),
                                                   'sampling_frequency': 1}})
            input_args.pop('NeuroscopeRecording')
            self.data_interface_classes = new_data_interface_classes
            self._recording_type = 'YutaNoRecording'
        else:
            self._recording_type = 'NeuroscopeRecording'
        super().__init__(**input_args)

    def get_recording_type(self):
        return self._recording_type

    def get_metadata(self):
        # TODO: could be vastly improved with pathlib
        session_path = self.data_interface_objects['NeuroscopeSorting'].input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)
        fpath_base = os.path.split(subject_path)[0]
        # TODO: improve mouse_number extraction
        mouse_number = session_id[9:11]
        # TODO: add error checking on file existence
        subject_xls = os.path.join(subject_path, 'YM' + mouse_number + ' exp_sheet.xlsx')
        hilus_csv_path = os.path.join(fpath_base, 'early_session_hilus_chans.csv')
        if '-' in session_id:
            subject_id, date_text = session_id.split('-')
            b = False
        else:
            subject_id, date_text = session_id.split('b')
            b = True

        session_start = dateparse(date_text, yearfirst=True)

        if os.path.isfile(subject_xls):
            subject_df = pd.read_excel(subject_xls)
            subject_data = {}
            for key in ['genotype', 'DOB', 'implantation', 'Probe', 'Surgery', 'virus injection', 'mouseID']:
                names = subject_df.iloc[:, 0]
                if key in names.values:
                    subject_data[key] = subject_df.iloc[np.argmax(names == key), 1]
            if isinstance(subject_data['DOB'], datetime):
                age = str(session_start - subject_data['DOB'])
            else:
                age = None
        else:
            # TODO: figure better way of handling this, espepcially since it also determines LFP type info
            age = 'unknown'
            subject_data = {}
            subject_data.update({'genotype': 'unknown'})
            print("Warning: no subject file detected!")

        # TODO: add error checking on file existence
        xml_filepath = os.path.join(session_path, session_id + '.xml')
        root = et.parse(xml_filepath).getroot()

        n_total_channels = int(root.find('acquisitionSystem').find('nChannels').text)
        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        nshanks = len(shank_channels)
        spikes_nsamples = int(root.find('neuroscope').find('spikes').find('nSamples').text)
        lfp_sampling_rate = float(root.find('fieldPotentials').find('lfpSamplingRate').text)

        lfp_channel = get_reference_elec(subject_xls,
                                         hilus_csv_path,
                                         session_start,
                                         session_id,
                                         b=b)
        shank_electrode_number = [x for _, channels in enumerate(shank_channels) for x, _ in enumerate(channels)]

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

        task_types = [
            {'name': 'OpenFieldPosition_ExtraLarge'},
            {'name': 'OpenFieldPosition_New_Curtain', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_New', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_Old_Curtain', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_Old', 'conversion': 0.46},
            {'name': 'OpenFieldPosition_Oldlast', 'conversion': 0.46},
            {'name': 'EightMazePosition', 'conversion': 0.65 / 2}
        ]

        # Would these special electrode have the same exact IDs across different sessions/experiments?
        # assuming so in the min() check below
        special_electrode_mapping = {'ch_wait': 79, 'ch_arm': 78, 'ch_solL': 76,
                                     'ch_solR': 77, 'ch_dig1': 65, 'ch_dig2': 68,
                                     'ch_entL': 72, 'ch_entR': 71, 'ch_SsolL': 73,
                                     'ch_SsolR': 70}
        special_electrodes = []
        for special_electrode_name, channel in special_electrode_mapping.items():
            if channel <= n_total_channels-1:
                special_electrodes.append({'name': special_electrode_name,
                                           'channel': channel,
                                           'description': 'environmental electrode recorded inline with neural data'})

        df_unit_features = get_UnitFeatureCell_features(fpath_base, session_id, session_path, nshanks)

        # there are occasional mismatches between the matlab struct
        # and the neuroscope files regions: 3: 'CA3', 4: 'DG'
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

        metadata = {
            'NWBFile': {
                'identifier': session_id,
                'session_start_time': session_start.astimezone(),
                'file_create_date': datetime.now().astimezone(),
                'session_id': session_id,
                'institution': 'NYU',
                'lab': 'Buzsaki'
            },
            'Subject': {
                'subject_id': subject_id,
                'age': age,
                'genotype': subject_data['genotype'],
                # should be Mus musculus? also not specified in the experiment file except by the phrase 'mouseID'
                'species': 'mouse'
            },
            self.get_recording_type(): {
                'Ecephys': {
                    'subset_channels': all_shank_channels,
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
                            'data':  list(all_shank_channels == lfp_channel)
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
                    'ElectricalSeries': {
                        'name': 'ElectricalSeries',
                        'description': 'raw acquisition traces'
                    }
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
                    }
                  ]
            },
            'YutaPosition': {
            },
            'YutaLFP': {
                'shank_channels': all_shank_channels,
                'nshanks': len(shank_channels),
                'special_electrodes': special_electrodes,
                'lfp_channel': lfp_channel,
                'lfp_sampling_rate': lfp_sampling_rate,
                'lfp': {'name': 'lfp',
                        'description': 'lfp signal for all shank electrodes'},
                'lfp_decomposition': {'name': 'LFPDecompositionSeries',
                                      'description': 'Theta and Gamma phase for reference LFP'},
                'spikes_nsamples': spikes_nsamples,
            },
            'YutaBehavior': {
                'task_types': task_types
            }
        }

        return metadata
