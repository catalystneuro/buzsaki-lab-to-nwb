"""Authors: Cody Baker and Ben Dichter."""
import os
import numpy as np

from lxml import etree as et
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile

from ..neuroscope import write_spike_waveforms


class PeyracheWaveformInterface(BaseDataInterface):
    """Primary data interface for LFP aspects of the PeyracheA dataset."""

    @classmethod
    def get_input_schema(cls):
        """Return subset of json schema for informing the NWBConverter of expepcted input arguments."""
        return dict(properties=dict(folder_path="string"))

    def convert_data(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        """Convert the LFP portion of a particular session of the PeyracheA dataset."""
        session_path = self.input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)
        if '_' in session_id:
            subject_id, date_text = session_id.split('_')

        xml_filepath = os.path.join(session_path, "{}.xml".format(session_id))
        root = et.parse(xml_filepath).getroot()

        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        spikes_nsamples = int(root.find('neuroscope').find('spikes').find('nSamples').text)

        subject_path, session_id = os.path.split(session_path)
        write_spike_waveforms(
            nwbfile,
            session_path,
            spikes_nsamples=spikes_nsamples,
            shank_channels=shank_channels,
            stub_test=stub_test
        )
