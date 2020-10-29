"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.utils import get_base_schema, get_schema_from_hdmf_class
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile, TimeSeries
from pynwb.misc import DecompositionSeries
import os
import numpy as np
import warnings

from ..band_analysis import filter_lfp, hilbert_lfp
from ..neuroscope import read_lfp, write_lfp, write_spike_waveforms, check_module


class GrosmarkLFPInterface(BaseDataInterface):

    @classmethod
    def get_input_schema(cls):
        return dict(properties=dict(folder_path="string"))

    def __init__(self, **input_args):
        super().__init__(**input_args)

    def get_metadata_schema(self):
        metadata_schema = get_base_schema()

        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['TimeSeries'] = get_schema_from_hdmf_class(TimeSeries)
        metadata_schema['properties']['DecompositionSeries'] = get_schema_from_hdmf_class(DecompositionSeries)
        required_fields = ['TimeSeries', 'DecompositionSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)

        return metadata_schema

    def convert_data(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
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
