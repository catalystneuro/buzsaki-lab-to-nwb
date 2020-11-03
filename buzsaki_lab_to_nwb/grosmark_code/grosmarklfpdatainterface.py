"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
import os
import warnings

from ..neuroscope import read_lfp, write_lfp, write_spike_waveforms


class GrosmarkLFPInterface(BaseDataInterface):
    """Primary data interface for LFP aspects of the GrosmarkAD dataset."""

    @classmethod
    def get_input_schema(cls):
        """Return subset of json schema for informing the NWBConverter of expepcted input arguments."""
        return dict(properties=dict(folder_path="string"))

    def convert_data(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        """Convert the LFP portion of a particular session of the GrosmarkAD dataset."""
        session_path = self.input_args['folder_path']
        all_shank_channels = metadata['all_shank_channels']
        lfp_sampling_rate = metadata['lfp_sampling_rate']
        spikes_nsamples = metadata['spikes_nsamples']
        shank_channels = metadata['shank_channels']
        n_total_channels = metadata['n_total_channels']

        subject_path, session_id = os.path.split(session_path)

        _, all_channels_lfp_data = read_lfp(session_path, stub=stub_test, n_channels=n_total_channels)
        try:
            lfp_data = all_channels_lfp_data[:, all_shank_channels]
        except IndexError:
            warnings.warn("Encountered indexing issue for all_shank_channels on lfp_data subsetting; using entire lfp!")
            lfp_data = all_channels_lfp_data
        write_lfp(
            nwbfile,
            lfp_data,
            lfp_sampling_rate,
            name=metadata['lfp']['name'],
            description=metadata['lfp']['description'],
            electrode_inds=None
        )
        write_spike_waveforms(
            nwbfile,
            session_path,
            spikes_nsamples=spikes_nsamples,
            shank_channels=shank_channels,
            stub_test=stub_test
        )
