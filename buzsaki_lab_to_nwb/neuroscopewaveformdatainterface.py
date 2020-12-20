"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from lxml import etree as et
import numpy as np

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile

from .neuroscope import write_spike_waveforms


class NeuroscopeWaveformInterface(BaseDataInterface):
    """Primary data interface for waveforms of the Neuroscope format (.spk files)."""

    @classmethod
    def get_source_schema(cls):
        """Return subset of json schema for informing the NWBConverter of expepcted input arguments."""
        return dict(properties=dict(folder_path={'type': "string"}))

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        """Convert the waveform portion of a particular Neuroscope session."""
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.stem
        if "_" in session_id:
            subject_id, date_text = session_id.split("_")

        xml_filepath = session_path / f"{session_id}.xml"
        root = et.parse(str(xml_filepath)).getroot()

        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        spikes_nsamples = int(root.find('neuroscope').find('spikes').find('nSamples').text)

        write_spike_waveforms(
            nwbfile,
            session_path,
            spikes_nsamples=spikes_nsamples,
            shank_channels=shank_channels,
            stub_test=stub_test
        )
