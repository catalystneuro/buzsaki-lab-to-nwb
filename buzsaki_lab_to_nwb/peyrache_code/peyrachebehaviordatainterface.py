"""Authors: Cody Baker and Ben Dichter."""
import os
import numpy as np
from pathlib import Path
from scipy.io import loadmat
import warnings

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.file import TimeIntervals
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..neuroscope import get_events, check_module


class PeyracheMiscInterface(BaseDataInterface):
    """Primary data interface for miscellaneous aspects of the PeyracheA dataset."""

    @classmethod
    def get_input_schema(cls):
        return dict(properties=dict(folder_path="string"))

    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict,
                     stub_test: bool = False, include_spike_waveforms: bool = False):
        session_path = self.input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)

        # Stimuli
        [nwbfile.add_stimulus(x) for x in get_events(session_path)]

        # States
        sleep_state_fpath = os.path.join(session_path, "{session_id}.SleepState.states.mat")
        # label renaming specific to Peyrache
        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        if os.path.isfile(sleep_state_fpath):
            matin = loadmat(sleep_state_fpath)['SleepState']['ints'][0][0]

            table = TimeIntervals(name='states', description="Sleep states of animal.")
            table.add_column(name='label', description="Sleep state.")

            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append(dict(start_time=row[0], stop_time=row[1], label=state_label_names[name]))
            [table.add_row(**row) for row in sorted(data, key=lambda x: x['start_time'])]
            check_module(nwbfile, 'behavior', 'contains behavioral data').add_data_interface(table)

        # Position
        pos_filepath = Path(session_path) / f"{session_id}.position.behavior.mat"
        pos_mat = loadmat(str(pos_filepath.absolute()))
        starting_time = float(pos_mat['position']['timestamps'][0][0][0])  # confirmed to be a regularly sampled series
        rate = float(pos_mat['position']['timestamps'][0][0][1]) - starting_time
        if pos_mat['position']['units'][0][0][0] == 'm':
            conversion = 1.0
        else:
            warnings.warn(f"Spatial units ({pos_mat['position']['units'][0][0][0]}) not listed in meters; "
                          "setting conversion to nan.")
            conversion = np.nan
        pos_data = [[x[0], y[0]] for x, y in zip(pos_mat['position']['position'][0][0]['x'][0][0],
                                                 pos_mat['position']['position'][0][0]['y'][0][0])]
        linearized_data = [[lin[0]] for lin in pos_mat['position']['position'][0][0]['lin'][0][0]]

        label = pos_mat['position']['behaviorinfo'][0][0]['MazeType'][0][0][0].replace(" ", "")
        pos_obj = Position(name=f"{label}Position")
        spatial_series_object = SpatialSeries(
            name=f"{label}SpatialSeries",
            description="(x,y) coordinates tracking subject movement through the maze.",
            data=H5DataIO(pos_data, compression='gzip'),
            reference_frame='unknown',
            conversion=conversion,
            starting_time=starting_time,
            rate=rate,
            resolution=np.nan
        )
        pos_obj.add_spatial_series(spatial_series_object)
        check_module(nwbfile, 'behavior', 'contains processed behavioral data').add_data_interface(pos_obj)

        lin_pos_obj = Position(name=f"{label}LinearizedPosition")
        lin_spatial_series_object = SpatialSeries(
            name=f"{label}LinearizedTimeSeries",
            description="Linearized position, defined as starting at the edge of reward area, "
            "and increasing clockwise, terminating at the opposing edge of the reward area.",
            data=H5DataIO(linearized_data, compression='gzip'),
            reference_frame='unknown',
            conversion=conversion,
            starting_time=starting_time,
            rate=rate,
            resolution=np.nan
        )
        lin_pos_obj.add_spatial_series(lin_spatial_series_object)
        check_module(nwbfile, 'behavior', 'contains processed behavioral data').add_data_interface(lin_pos_obj)

        # Epochs
        epoch_names = list(pos_mat['position']['Epochs'][0][0].dtype.names)
        epoch_windows = [[float(start), float(stop)]
                         for x in pos_mat['position']['Epochs'][0][0][0][0] for start, stop in x]
        nwbfile.add_epoch_column('label', 'name of epoch')
        for j, epoch_name in enumerate(epoch_names):
            nwbfile.add_epoch(start_time=epoch_windows[j][0], stop_time=epoch_windows[j][1], label=epoch_name)
