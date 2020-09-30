"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools import NWBConverter, neuroscopedatainterface
from .watsonlfpdatainterface import WatsonLFPInterface
from .watsonbehaviordatainterface import WatsonBehaviorInterface
from .watsonnorecording import WatsonNoRecording
import pandas as pd
import numpy as np
from scipy.io import loadmat
import os
from lxml import etree as et
from datetime import datetime
from dateutil.parser import parse as dateparse
from ..neuroscope import get_clusters_single_shank, read_spike_clustering


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

            session_id = os.path.split(input_args['NeuroscopeSorting']['folder_path'])[1]
            xml_filepath = os.path.join(input_args['NeuroscopeSorting']['folder_path'], session_id + '.xml')
            root = et.parse(xml_filepath).getroot()
            n_channels = len([[int(channel.text)
                              for channel in group.find('channels')]
                              for group in root.find('spikeDetection').find('channelGroups').findall('group')])
            # The only information needed for this is .get_channel_ids() which is set by the shape of the input series
            input_args.update({'WatsonNoRecording': {'timeseries': np.array(range(n_channels)),
                                                     'sampling_frequency': 1}})
            input_args.pop('NeuroscopeRecording')
            self.data_interface_classes = new_data_interface_classes
            self._recording_type = 'WatsonNoRecording'
        else:
            self._recording_type = 'NeuroscopeRecording'
        super().__init__(**input_args)

    def get_recording_type(self):
        return self._recording_type

    def get_metadata(self):
        # TODO: could be vastly improved with pathlib
        session_path = self.data_interface_objects['NeuroscopeSorting'].input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)
        if '_' in session_id:
            subject_id, date_text = session_id.split('_')
        session_start = dateparse(date_text)

        # TODO: add error checking on file existence
        xml_filepath = os.path.join(session_path, session_id + '.xml')
        root = et.parse(xml_filepath).getroot()

        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        spikes_nsamples = int(root.find('neuroscope').find('spikes').find('nSamples').text)
        lfp_sampling_rate = float(root.find('fieldPotentials').find('lfpSamplingRate').text)

        session_info_filepath = os.path.join(session_path, session_id, ".sessionInfo.mat")
        if os.path.isfile(session_info_filepath):
            sw_reference = loadmat(session_info_filepath)['sessionInfo']['channelTags'][0][0]['SWChan'][0][0][0][0]

        basic_metadata_filepath = os.path.join(session_path, session_id, "_BasicMetaData.mat")
        if os.path.isfile(basic_metadata_filepath):
            matin = loadmat(basic_metadata_filepath)['bmd']
            up_reference = matin['UPstatechannel'][0][0][0][0]
            spindle_reference = matin['Spindlechannel'][0][0][0][0]
            theta_reference = matin['Thetachannel'][0][0][0][0]

        shank_electrode_number = [x for _, channels in enumerate(shank_channels) for x, _ in enumerate(channels)]

        cell_filepath = os.path.join(session_path, session_id, ".spikes.cellinfo.mat")
        if os.path.isfile(cell_filepath):
            cell_info = loadmat(cell_filepath)['spikes']

        celltype_mapping = {'pE': "excitatory", 'pI': "inhibitory"}
        celltype_filepath = os.path.join(session_path, session_id, ".CellClass.cellinfo.mat")
        if os.path.isfile(celltype_filepath):
            celltype_info = [celltype_mapping[x[0]] for x in loadmat(celltype_filepath)['CellClass']['label'][0][0][0]]

        device_name = "implant"

        if os.path.isfile(basic_metadata_filepath):
            cortex_region = loadmat(basic_metadata_filepath)['CortexRegion'][0][0][0]
        else:
            cortex_region = "unknown"

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
                            'name': 'sw_reference',
                            'description': 'this electrode was used to calculate slow-wave sleep',
                            'data':  list(all_shank_channels == sw_reference)
                        },
                        {
                            'name': 'up_reference',
                            'description': 'this electrode was used to calculate slow-wave sleep',
                            'data':  list(all_shank_channels == up_reference)
                        },
                        {
                            'name': 'spindle_reference',
                            'description': 'this electrode was used to calculate slow-wave sleep',
                            'data':  list(all_shank_channels == spindle_reference)
                        },
                        {
                            'name': 'theta_reference',
                            'description': 'this electrode was used to calculate slow-wave sleep',
                            'data':  list(all_shank_channels == theta_reference)
                        },
                        {
                            'name': 'shank_electrode_number',
                            'description': '0-indexed channel within a shank',
                            'data': shank_electrode_number
                        }
                    ],
                    'ElectricalSeries': {
                        'name': 'ElectricalSeries',
                        'description': 'raw acquisition traces'
                    }
                }
            },
            'NeuroscopeSorting': {
                # TODO: should add if checks for conditions on whether these metadata were instantiated earlier
                'UnitProperties': [
                    {
                        'name': 'cell_type',
                        'description': 'name of cell type',
                        'data': celltype_info
                    },
                    {
                        'name': 'global_id',
                        'description': 'global id for cell for entire experiment',
                        'data': list(cell_info['UID'][0][0][0])
                    },
                    {
                        'name': 'shank_id',
                        'description': '0-indexed id of cluster from shank',
                        # - 2 b/c the 0 and 1 IDs from each shank have been removed
                        'data': [x - 2 for x in cell_info['cluID'][0][0][0]]
                    },
                    {
                        'name': 'electrode_group',
                        'description': 'the electrode group that each spike unit came from',
                        'data': list(cell_info['shankID'][0][0][0])
                    },
                    {
                        'name': 'region',
                        'description': 'brain region where unit was detected',
                        'data': [x[0] for x in cell_info['region'][0][0][0]]
                    }
                  ]
            },
            'WatsonLFP': {
                'all_shank_channels': all_shank_channels,
                'lfp_channels': {'sw_reference': sw_reference,
                                 'up_reference': up_reference,
                                 'spindle_reference': spindle_reference,
                                 'theta_reference': theta_reference},
                'lfp_sampling_rate': lfp_sampling_rate,
                'lfp': {'name': 'lfp',
                        'description': 'lfp signal for all shank electrodes'},
                'lfp_decomposition': {'sw_reference': {'name': 'SWDecompositionSeries',
                                                       'description': 'Theta and Gamma phase for sw-reference LFP'},
                                      'up_reference': {'name': 'UPDecompositionSeries',
                                                       'description': 'Theta and Gamma phase for up-reference LFP'},
                                      'spindle_reference': {'name': 'SpindleDecompositionSeries',
                                                            'description':
                                                                'Theta and Gamma phase for spindle-reference LFP'},
                                      'theta_reference': {'name': 'ThetaDecompositionSeries',
                                                          'description':
                                                              'Theta and Gamma phase for theta-reference LFP'}},
                'spikes_nsamples': spikes_nsamples,
                'shank_channels': shank_channels
            },
            'WatsonBehavior': {
            }
        }

        return metadata
