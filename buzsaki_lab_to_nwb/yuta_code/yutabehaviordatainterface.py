"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.utils import get_base_schema, get_schema_from_hdmf_class
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.file import TimeIntervals
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO
import os
import numpy as np
from scipy.io import loadmat
from ..neuroscope import get_events, find_discontinuities, check_module


class YutaBehaviorInterface(BaseDataInterface):

    @classmethod
    def get_input_schema(cls):
        return dict(
            required=['folder_path'],
            properties=dict(
                folder_path=dict(type='string')
            )
        )

    def __init__(self, **input_args):
        super().__init__(**input_args)

    def get_metadata_schema(self):
        metadata_schema = get_base_schema()

        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['SpatialSeries'] = get_schema_from_hdmf_class(SpatialSeries)
        required_fields = ['SpatialSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)

        return metadata_schema

    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict,
                     stub_test: bool = False, include_spike_waveforms: bool = False):
        session_path = self.input_args['folder_path']
        # TODO: check/enforce format?
        task_types = metadata_dict['task_types']

        subject_path, session_id = os.path.split(session_path)

        [nwbfile.add_stimulus(x) for x in get_events(session_path)]

        sleep_state_fpath = os.path.join(session_path, '{}--StatePeriod.mat'.format(session_id))

        exist_pos_data = any(os.path.isfile(os.path.join(session_path,
                                                         '{}__{}.mat'.format(session_id, task_type['name'])))
                             for task_type in task_types)

        if exist_pos_data:
            nwbfile.add_epoch_column('label', 'name of epoch')

        for task_type in task_types:
            label = task_type['name']

            file = os.path.join(session_path, session_id + '__' + label + '.mat')
            if os.path.isfile(file):
                pos_obj = Position(name=label + '_position')

                matin = loadmat(file)
                tt = matin['twhl_norm'][:, 0]
                exp_times = find_discontinuities(tt)

                if 'conversion' in task_type:
                    conversion = task_type['conversion']
                else:
                    conversion = np.nan

                for pos_type in ('twhl_norm', 'twhl_linearized'):
                    if pos_type in matin:
                        pos_data_norm = matin[pos_type][:, 1:]

                        spatial_series_object = SpatialSeries(
                            name=label + '_{}_spatial_series'.format(pos_type),
                            data=H5DataIO(pos_data_norm, compression='gzip'),
                            reference_frame='unknown', conversion=conversion,
                            resolution=np.nan,
                            timestamps=H5DataIO(tt, compression='gzip'))
                        pos_obj.add_spatial_series(spatial_series_object)

                check_module(nwbfile, 'behavior', 'contains processed behavioral data').add_data_interface(pos_obj)
                for i, window in enumerate(exp_times):
                    nwbfile.add_epoch(start_time=window[0], stop_time=window[1],
                                      label=label + '_' + str(i))

        trialdata_path = os.path.join(session_path, session_id + '__EightMazeRun.mat')
        if os.path.isfile(trialdata_path):
            trials_data = loadmat(trialdata_path)['EightMazeRun']

            trialdatainfo_path = os.path.join(subject_path, 'EightMazeRunInfo.mat')
            trialdatainfo = [x[0] for x in loadmat(trialdatainfo_path)['EightMazeRunInfo'][0]]

            features = trialdatainfo[:7]
            features[:2] = 'start_time', 'stop_time',
            [nwbfile.add_trial_column(x, 'description') for x in features[4:] + ['condition']]

            for trial_data in trials_data:
                if trial_data[3]:
                    cond = 'run_left'
                else:
                    cond = 'run_right'
                nwbfile.add_trial(start_time=trial_data[0], stop_time=trial_data[1], condition=cond,
                                  error_run=trial_data[4], stim_run=trial_data[5], both_visit=trial_data[6])

        if os.path.isfile(sleep_state_fpath):
            matin = loadmat(sleep_state_fpath)['StatePeriod']

            table = TimeIntervals(name='states', description='sleep states of animal')
            table.add_column(name='label', description='sleep state')

            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append({'start_time': row[0], 'stop_time': row[1], 'label': name})
            [table.add_row(**row) for row in sorted(data, key=lambda x: x['start_time'])]

            check_module(nwbfile, 'behavior', 'contains behavioral data').add_data_interface(table)
