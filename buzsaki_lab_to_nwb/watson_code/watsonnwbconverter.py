"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from nwb_conversion_tools import NWBConverter, neuroscopedatainterface
from .watsonlfpdatainterface import WatsonLFPInterface
from .watsonbehaviordatainterface import WatsonBehaviorInterface
from .watsonnorecording import WatsonNoRecording
from .watsonsortinginterface import WatsonSortingInterface
import numpy as np
from scipy.io import loadmat
import os
from lxml import etree as et
from datetime import datetime
from dateutil.parser import parse as dateparse
from ..neuroscope import get_clusters_single_shank


class WatsonNWBConverter(NWBConverter):
    # The order of this dictionary matter significantly, but python dictionaries are supposed to be unordered
    # This is compensated for the time being, but should this conceptually be a list instead?
    data_interface_classes = {'NeuroscopeRecording': neuroscopedatainterface.NeuroscopeRecordingInterface,
                              'NeuroscopeSorting': neuroscopedatainterface.NeuroscopeSortingInterface,
                              'WatsonLFP': WatsonLFPInterface,
                              'WatsonBehavior': WatsonBehaviorInterface}

    def __init__(self, **input_args):
        dat_filepath = input_args.get('NeuroscopeRecording', {}).get('file_path', None)
        if not os.path.isfile(dat_filepath):
            new_data_interface_classes = {}

            new_data_interface_classes.update({'WatsonNoRecording': WatsonNoRecording})
            for name, val in self.data_interface_classes.items():
                new_data_interface_classes.update({name: val})
            new_data_interface_classes.pop('NeuroscopeRecording')

            session_id = os.path.split(input_args['WatsonLFP']['folder_path'])[1]
            xml_filepath = os.path.join(input_args['WatsonLFP']['folder_path'], session_id + '.xml')
            root = et.parse(xml_filepath).getroot()
            n_channels = len([int(channel.text)
                              for group in root.find('spikeDetection').find('channelGroups').findall('group')
                              for channel in group.find('channels')])
            # The only information needed for this is .get_channel_ids() which is set by the shape of the input series
            input_args.update({'WatsonNoRecording': {'timeseries': np.array(range(n_channels)),
                                                     'sampling_frequency': 1}})
            input_args.pop('NeuroscopeRecording')
            self.data_interface_classes = new_data_interface_classes
            self._recording_type = 'WatsonNoRecording'
        else:
            self._recording_type = 'NeuroscopeRecording'
            
        # Very special case for only one session
        special_sorting = input_args.get('CellExplorerSorting', None)
        if special_sorting is not None:
            self.data_interface_classes.pop('NeuroscopeSorting')
            self.data_interface_classes.update({'CellExplorerSorting': WatsonSortingInterface})
            self._sorting_type = 'CellExplorerSorting'
        else:
            self._sorting_type = 'NeuroscopeSorting'
        super().__init__(**input_args)

    def get_recording_type(self):
        return self._recording_type
    
    def get_sorting_type(self):
        return self._sorting_type

    def get_metadata(self):
        # TODO: could be vastly improved with pathlib
        session_path = self.data_interface_objects['WatsonLFP'].input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)
        if '_' in session_id:
            subject_id, date_text = session_id.split('_')
        session_start = dateparse(date_text)

        # TODO: add error checking on file existence
        xml_filepath = os.path.join(session_path, "{}.xml".format(session_id))
        root = et.parse(xml_filepath).getroot()

        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        spikes_nsamples = int(root.find('neuroscope').find('spikes').find('nSamples').text)
        lfp_sampling_rate = float(root.find('fieldPotentials').find('lfpSamplingRate').text)

        session_info_filepath = os.path.join(session_path, "{}.sessionInfo.mat".format(session_id))
        if os.path.isfile(session_info_filepath):
            n_total_channels = loadmat(session_info_filepath)['sessionInfo']['nChannels'][0][0][0][0]

        basic_metadata_filepath = os.path.join(session_path, "{}_BasicMetaData.mat".format(session_id))
        if os.path.isfile(basic_metadata_filepath):
            matin = loadmat(basic_metadata_filepath)['bmd']
            up_reference = matin['UPstatechannel'][0][0][0][0]
            spindle_reference = matin['Spindlechannel'][0][0][0][0]
            theta_reference = matin['Thetachannel'][0][0][0][0]

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

        if os.path.isfile(basic_metadata_filepath):
            cortex_region = loadmat(basic_metadata_filepath)['CortexRegion'][0][0][0]
        else:
            cortex_region = "unknown"

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
                        'location': cortex_region,
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
                    'ElectricalSeries': {
                        'name': 'ElectricalSeries',
                        'description': 'raw acquisition traces'
                    }
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
            'WatsonLFP': {
                'all_shank_channels': all_shank_channels,
                'lfp_channels': {},
                'lfp_sampling_rate': lfp_sampling_rate,
                'lfp': {'name': 'lfp',
                        'description': 'lfp signal for all shank electrodes'},
                'lfp_decomposition': {},
                'spikes_nsamples': spikes_nsamples,
                'shank_channels': shank_channels,
                'n_total_channels': n_total_channels
            },
            'WatsonBehavior': {
            }
        }

        # If reference channels are auto-detected for a given session, add them to the various metadata fields
        test_list = list(all_shank_channels == up_reference)
        if any(test_list):
            metadata[self.get_recording_type()]['Ecephys']['Electrodes'].append({
                'name': 'up_reference',
                'description': 'this electrode was used to calculate UP-states',
                'data':  test_list
            })
            metadata['WatsonLFP']['lfp_channels'].update({'up_reference': up_reference})
            metadata['WatsonLFP']['lfp_decomposition'].update({
                'up_reference': {'name': 'UPDecompositionSeries',
                                 'description': 'Theta and Gamma phase for up-reference LFP'}
            })

        test_list = list(all_shank_channels == spindle_reference)
        if any(test_list):
            metadata[self.get_recording_type()]['Ecephys']['Electrodes'].append({
                'name': 'spindle_reference',
                'description': 'this electrode was used to calculate slow-wave sleep',
                'data':  test_list
            })
            metadata['WatsonLFP']['lfp_channels'].update({'spindle_reference': spindle_reference})
            metadata['WatsonLFP']['lfp_decomposition'].update({
                'spindle_reference': {'name': 'SpindleDecompositionSeries',
                                      'description': 'Theta and Gamma phase for spindle-reference LFP'}
            })

        test_list = list(all_shank_channels == theta_reference)
        if any(test_list):
            metadata[self.get_recording_type()]['Ecephys']['Electrodes'].append({
                'name': 'theta_reference',
                'description': 'this electrode was used to calculate theta canonical bands',
                'data':  test_list
            })
            metadata['WatsonLFP']['lfp_channels'].update({'theta_reference': theta_reference})
            metadata['WatsonLFP']['lfp_decomposition'].update({
                'theta_reference': {'name': 'ThetaDecompositionSeries',
                                    'description': 'Theta and Gamma phase for theta-reference LFP'}
            })

        # If there is missing auto-detected metadata for unit properties, truncate those units from the extractor
        se_ids = set(self.data_interface_objects[self.get_sorting_type()].sorting_extractor.get_unit_ids())
        if len(celltype_info) < len(se_ids):
            defaults = {'cell_type': "unknown", 'region': "unknown"}
            missing_ids = se_ids - set(np.arange(len(celltype_info)))
            unit_map = self.data_interface_objects[self.get_sorting_type()].sorting_extractor._unit_map
            for missing_id in missing_ids:
                metadata[self.get_sorting_type()]['UnitProperties'][0]['data'].append(defaults['cell_type'])
                metadata[self.get_sorting_type()]['UnitProperties'][1]['data'].append(int(missing_id))
                metadata[self.get_sorting_type()]['UnitProperties'][2]['data'].append(int(unit_map[missing_id]['unit_id']
                                                                                      - 1))
                metadata[self.get_sorting_type()]['UnitProperties'][3]['data'].append(
                    "shank{}".format(unit_map[missing_id]['sorting_id']))
                metadata[self.get_sorting_type()]['UnitProperties'][4]['data'].append(defaults['region'])

        return metadata
