"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from nwb_conversion_tools import NWBConverter, neuroscopedatainterface
from .grosmarklfpdatainterface import GrosmarkLFPInterface
from .grosmarkbehaviordatainterface import GrosmarkBehaviorInterface
from .grosmarknorecording import GrosmarkNoRecording
# from .grosmarksortinginterface import GrosmarkSortingInterface
import numpy as np
from scipy.io import loadmat
import os
from lxml import etree as et
from datetime import datetime
from dateutil.parser import parse as dateparse


class GrosmarkNWBConverter(NWBConverter):
    data_interface_classes = {'GrosmarkNoRecording': GrosmarkNoRecording,
                               # 'NeuroscopeSorting': neuroscopedatainterface.NeuroscopeSortingInterface,
                              'GrosmarkLFP': GrosmarkLFPInterface,
                              'GrosmarkBehavior': GrosmarkBehaviorInterface}

    def __init__(self, **input_args):
        self._recording_type = 'GrosmarkNoRecording'
        session_id = os.path.split(input_args['GrosmarkLFP']['folder_path'])[1]
        xml_filepath = os.path.join(input_args['GrosmarkLFP']['folder_path'], session_id + '.xml')
        root = et.parse(xml_filepath).getroot()
        n_channels = len([int(channel.text)
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')
                          for channel in group.find('channels')])
        input_args.update(
            GrosmarkNoRecording=dict(
                timeseries=np.array(range(n_channels)),
                sampling_frequency=1
            )
        )
        # Very special case for only one session
        # special_sorting = input_args.get('CellExplorerSorting', None)
        # if special_sorting is not None:
        #     self.data_interface_classes.pop('NeuroscopeSorting')
        #     self.data_interface_classes.update({'CellExplorerSorting': GrosmarkSortingInterface})
        #     self._sorting_type = 'CellExplorerSorting'
        # else:
        self._sorting_type = 'NeuroscopeSorting'
        super().__init__(**input_args)

    def get_recording_type(self):
        return self._recording_type

    def get_sorting_type(self):
        return self._sorting_type

    def get_metadata(self):
        session_path = self.data_interface_objects['GrosmarkLFP'].input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)
        if '_' in session_id:
            subject_id, date_text = session_id.split('_')
        session_start = dateparse(date_text[-4:] + date_text[:-4])

        xml_filepath = os.path.join(session_path, "{}.xml".format(session_id))
        root = et.parse(xml_filepath).getroot()

        n_total_channels = int(root.find('acquisitionSystem').find('nChannels').text)
        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        spikes_nsamples = int(root.find('neuroscope').find('spikes').find('nSamples').text)
        lfp_sampling_rate = float(root.find('fieldPotentials').find('lfpSamplingRate').text)

        shank_electrode_number = [x for channels in shank_channels for x, _ in enumerate(channels)]
        shank_group_name = ["shank{}".format(n+1) for n, channels in enumerate(shank_channels) for _ in channels]

        cell_filepath = os.path.join(session_path, "{}.spikes.cellinfo.mat".format(session_id))
        if os.path.isfile(cell_filepath):
            cell_info = loadmat(cell_filepath)['spikes']

        celltype_mapping = {'pE': "excitatory", 'pI': "inhibitory"}
        celltype_filepath = os.path.join(session_path, "{}.CellClass.cellinfo.mat".format(session_id))
        if os.path.isfile(celltype_filepath):
            celltype_info = [str(celltype_mapping[x[0]])
                             for x in loadmat(celltype_filepath)['CellClass']['label'][0][0][0]]

        device_name = "implant"
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
            },
            self.get_recording_type(): {
                'Ecephys': {
                    'subset_channels': all_shank_channels,
                    'Device': [{
                        'name': device_name
                    }],
                    'ElectrodeGroup': [{
                        'name': f'shank{n+1}',
                        'description': f'shank{n+1} electrodes',
                        'device_name': device_name
                    } for n, _ in enumerate(shank_channels)],
                    'Electrodes': [
                        {
                            'name': 'shank_electrode_number',
                            'description': '0-indexed channel within a shank',
                            'data': shank_electrode_number
                        },
                        {
                            'name': 'group',
                            'description': 'a reference to the ElectrodeGroup this electrode is a part of',
                            'data': shank_group_name
                        },
                        {
                            'name': 'group_name',
                            'description': 'the name of the ElectrodeGroup this electrode is a part of',
                            'data': shank_group_name
                        }
                    ],
                }
            },
            self.get_sorting_type(): {
                'UnitProperties': [
                    {
                        'name': 'cell_type',
                        'description': 'name of cell type',
                        'data': celltype_info
                    },
                    {
                        'name': 'global_id',
                        'description': 'global id for cell for entire experiment',
                        'data': [int(x) for x in cell_info['UID'][0][0][0]]
                    },
                    {
                        'name': 'shank_id',
                        'description': '0-indexed id of cluster from shank',
                        # - 2 b/c the 0 and 1 IDs from each shank have been removed
                        'data': [int(x - 2) for x in cell_info['cluID'][0][0][0]]
                    },
                    {
                        'name': 'electrode_group',
                        'description': 'the electrode group that each spike unit came from',
                        'data': ["shank" + str(x) for x in cell_info['shankID'][0][0][0]]
                    },
                    {
                        'name': 'region',
                        'description': 'brain region where unit was detected',
                        'data': [str(x[0]) for x in cell_info['region'][0][0][0]]
                    }
                  ]
            },
            'GrosmarkLFP': {
                'all_shank_channels': all_shank_channels,
                'lfp_sampling_rate': lfp_sampling_rate,
                'lfp': {'name': 'lfp',
                        'description': 'lfp signal for all shank electrodes'},
                'spikes_nsamples': spikes_nsamples,
                'shank_channels': shank_channels,
                'n_total_channels': n_total_channels
            },
            'GrosmarkBehavior': {
            }
        }

        # If there is missing auto-detected metadata for unit properties, truncate those units from the extractor
        # se_ids = set(self.data_interface_objects[self.get_sorting_type()].sorting_extractor.get_unit_ids())
        # if len(celltype_info) < len(se_ids):
        #     defaults = {'cell_type': "unknown", 'region': "unknown"}
        #     missing_ids = se_ids - set(np.arange(len(celltype_info)))
        #     unit_map = self.data_interface_objects[self.get_sorting_type()].sorting_extractor._unit_map
        #     for missing_id in missing_ids:
        #         metadata[self.get_sorting_type()]['UnitProperties'][0]['data'].append(defaults['cell_type'])
        #         metadata[self.get_sorting_type()]['UnitProperties'][1]['data'].append(int(missing_id))
        #         metadata[self.get_sorting_type()]['UnitProperties'][2]['data'].append(int(unit_map[missing_id]['unit_id']
        #                                                                               - 1))
        #         metadata[self.get_sorting_type()]['UnitProperties'][3]['data'].append(
        #             "shank{}".format(unit_map[missing_id]['sorting_id']))
        #         metadata[self.get_sorting_type()]['UnitProperties'][4]['data'].append(defaults['region'])

        return metadata
