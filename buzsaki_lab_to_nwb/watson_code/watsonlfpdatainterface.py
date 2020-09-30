"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.utils import get_base_schema, get_schema_from_hdmf_class
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile, TimeSeries
from pynwb.misc import DecompositionSeries
import os
import numpy as np

from ..band_analysis import filter_lfp, hilbert_lfp
from ..neuroscope import read_lfp, write_lfp, write_spike_waveforms, check_module


class WatsonLFPInterface(BaseDataInterface):

    @classmethod
    def get_input_schema(cls):
        return {}


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

    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict, stub_test: bool = False):
        session_path = self.input_args['folder_path']
        # TODO: check/enforce format?
        all_shank_channels = metadata_dict['all_shank_channels']
        special_electrode_dict = metadata_dict.get('special_electrodes', None)
        lfp_channels = metadata_dict['lfp_channels']
        lfp_sampling_rate = metadata_dict['lfp_sampling_rate']
        spikes_nsamples = metadata_dict['spikes_nsamples']
        shank_channels = metadata_dict['shank_channels']

        subject_path, session_id = os.path.split(session_path)

        _, all_channels_lfp_data = read_lfp(session_path, stub=stub_test)
        lfp_data = all_channels_lfp_data[:, all_shank_channels]
        lfp_ts = write_lfp(nwbfile, lfp_data, lfp_sampling_rate,
                           name=metadata_dict['lfp']['name'],
                           description=metadata_dict['lfp']['description'],
                           electrode_inds=None)

        # TODO: error checking on format?
        for special_electrode in special_electrode_dict:
            ts = TimeSeries(name=special_electrode['name'],
                            description=special_electrode['description'],
                            data=all_channels_lfp_data[:, special_electrode['channel']],
                            rate=lfp_sampling_rate, unit='V', resolution=np.nan)
            nwbfile.add_acquisition(ts)

        for ref_name, lfp_channel in lfp_channels.items():
            all_lfp_phases = []
            for passband in ('theta', 'gamma'):
                lfp_fft = filter_lfp(lfp_data[:, all_shank_channels == lfp_channel].ravel(),
                                     lfp_sampling_rate,
                                     passband=passband)
                lfp_phase, _ = hilbert_lfp(lfp_fft)
                all_lfp_phases.append(lfp_phase[:, np.newaxis])
            decomp_series_data = np.dstack(all_lfp_phases)

            # TODO: should units or metrics be metadata?
            decomp_series = DecompositionSeries(name=metadata_dict['lfp_decomposition'][ref_name]['name'],
                                                description=metadata_dict['lfp_decomposition'][ref_name]['description'],
                                                data=decomp_series_data,
                                                rate=lfp_sampling_rate,
                                                source_timeseries=lfp_ts,
                                                metric='phase', unit='radians')
            # TODO: the band limits should be extracted from parse_passband in band_analysis?
            decomp_series.add_band(band_name='theta', band_limits=(4, 10))
            decomp_series.add_band(band_name='gamma', band_limits=(30, 80))

            check_module(nwbfile, 'ecephys',
                         'contains processed extracellular electrophysiology data').add_data_interface(decomp_series)

        write_spike_waveforms(nwbfile, session_path, spikes_nsamples=spikes_nsamples, shank_channels=shank_channels,
                              stub_test=stub_test)
