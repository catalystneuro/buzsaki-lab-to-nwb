"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools import NWBConverter, neuroscopedatainterface
from .grosmarklfpdatainterface import GrosmarkLFPInterface
from .grosmarkbehaviordatainterface import GrosmarkBehaviorInterface
from ..buzsakinorecording import BuzsakiNoRecording
import numpy as np
from scipy.io import loadmat
import os
from lxml import etree as et
from datetime import datetime
from dateutil.parser import parse as dateparse


class GrosmarkNWBConverter(NWBConverter):
    """Primary conversion class for the GrosmarkAD dataset."""

    data_interface_classes = {'BuzsakiNoRecording': BuzsakiNoRecording,
                              # 'NeuroscopeSorting': neuroscopedatainterface.NeuroscopeSortingInterface,
                              'GrosmarkLFP': GrosmarkLFPInterface,
                              'GrosmarkBehavior': GrosmarkBehaviorInterface}

    def __init__(self, **input_args):
        self._recording_type = 'BuzsakiNoRecording'
        session_id = os.path.split(input_args['GrosmarkLFP']['folder_path'])[1]
        xml_filepath = os.path.join(input_args['GrosmarkLFP']['folder_path'], session_id + '.xml')
        root = et.parse(xml_filepath).getroot()
        n_channels = len([int(channel.text)
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')
                          for channel in group.find('channels')])
        input_args.update(
            BuzsakiNoRecording=dict(
                timeseries=np.array(range(n_channels)),
                sampling_frequency=1
            )
        )
        self._sorting_type = 'NeuroscopeSorting'
        super().__init__(**input_args)

    def get_recording_type(self):
        """Auxilliary function for returning internal recording type."""
        return self._recording_type

    def get_metadata(self):
        """Auto-fill all relevant metadata used in run_conversion."""
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
        metadata = dict(
            NWBFile=dict(
                identifier=session_id,
                session_start_time=session_start.astimezone(),
                file_create_date=datetime.now().astimezone(),
                session_id=session_id,
                institution="NYU",
                lab="Buzsaki"
            ),
            Subject=dict(
                species="Rattus norvegicus domestica - Long Evans",
                genotype="Wild type",
                sex="male",
                weight="250-350g"
            )
        )

        return metadata
