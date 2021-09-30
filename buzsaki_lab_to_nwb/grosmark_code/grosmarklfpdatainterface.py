"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
import os
import warnings
from lxml import etree as et
import numpy as np

from ..utils.neuroscope import read_lfp, write_lfp, write_spike_waveforms


class GrosmarkLFPInterface(BaseDataInterface):
    """Primary data interface for LFP aspects of the GrosmarkAD dataset."""

    @classmethod
    def get_input_schema(cls):
        """Return subset of json schema for informing the NWBConverter of expepcted input arguments."""
        return dict(properties=dict(folder_path="string"))

    def convert_data(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        """Convert the LFP portion of a particular session of the GrosmarkAD dataset."""
        session_path = self.input_args["folder_path"]
        subject_path, session_id = os.path.split(session_path)
        if "_" in session_id:
            subject_id, date_text = session_id.split("_")

        xml_filepath = os.path.join(session_path, "{}.xml".format(session_id))
        root = et.parse(xml_filepath).getroot()

        shank_channels = [
            [int(channel.text) for channel in group.find("channels")]
            for group in root.find("spikeDetection").find("channelGroups").findall("group")
        ]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        lfp_sampling_rate = float(root.find("fieldPotentials").find("lfpSamplingRate").text)
        spikes_nsamples = int(root.find("neuroscope").find("spikes").find("nSamples").text)

        subject_path, session_id = os.path.split(session_path)

        _, all_channels_lfp_data = read_lfp(session_path, stub=stub_test)
        try:
            lfp_data = all_channels_lfp_data[:, all_shank_channels]
        except IndexError:
            warnings.warn("Encountered indexing issue for all_shank_channels on lfp_data subsetting; using entire lfp!")
            lfp_data = all_channels_lfp_data
        write_lfp(
            nwbfile,
            lfp_data,
            lfp_sampling_rate,
            name="lfp",
            description="lfp signal for all shank electrodes",
            electrode_inds=None,
        )
        write_spike_waveforms(
            nwbfile,
            session_path,
            spikes_nsamples=spikes_nsamples,
            shank_channels=shank_channels,
            stub_test=stub_test,
        )
