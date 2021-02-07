"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
from pathlib import Path
from hdf5storage import loadmat  # scipy.io loadmat doesn't support >= v7.3 matlab files
import pandas as pd

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile, TimeSeries
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..neuroscope import check_module


class PetersenMiscInterface(BaseDataInterface):
    """Primary data interface for miscellaneous aspects of the PetersenP dataset."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(folder_path=dict(type="string")))

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata_dict: dict,
        stub_test: bool = False,
     ):
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.name

        # Trials
        take_file_path = [x for x in session_path.iterdir() if "Take" in x.name][0]
        take_file = pd.read_csv(take_file_path, header=5)
        take_frame_to_time = {x: y for x, y in zip(take_file['Frame'], take_file['Time (Seconds)'])}

        trial_info = loadmat(str(session_path / f"{session_id}.trials.behavior.mat"))['trials']
        trial_start_frames = trial_info['start'][0][0]
        n_trials = len(trial_start_frames)
        trial_end_frames = trial_info['end'][0][0]
        trial_stat = trial_info['stat'][0][0]
        trial_stat_labels = [x[0][0] for x in trial_info['labels'][0][0]]
        trial_temperature = trial_info['temperature'][0][0]
        trial_error = trial_info['error'][0][0]
        error_trials = np.array([False]*n_trials)
        error_trials[np.array(trial_error).astype(int)] = True

        trial_starts = []
        trial_ends = []
        trial_condition = []
        for k in range(n_trials):
            trial_starts.append(take_frame_to_time[trial_start_frames[k]])
            trial_ends.append(take_frame_to_time[trial_end_frames[k]])
            nwbfile.add_trial(start_time=trial_starts[k], stop_time=trial_ends[k])
            trial_condition.append(trial_stat_labels[int(trial_stat[k])-1])

        nwbfile.add_trial_column(
            name='condition',
            description="Whether the maze condition was left or right.",
            data=trial_condition
        )
        nwbfile.add_trial_column(
            name='error',
            description="Whether the subject made a mistake.",
            data=error_trials
        )
        nwbfile.add_trial_column(
            name='temperature',
            description="Average brain temperature for the trial.",
            data=trial_temperature
        )

        # Epoch
        session_info = loadmat(str(session_path / "session.mat"))['session']
        nwbfile.add_epoch(
            start_time=trial_starts[0],
            stop_time=trial_ends[-1],
            tags=[session_info['epochs'][0][0]['mazeType'][0][0][0][0]]
        )

        # Position
        behavioral_processing_module = check_module(nwbfile, 'behavior', 'Contains processed behavioral data.')

        animal_file_path = session_path / "animal.mat"
        animal_mat = loadmat(str(animal_file_path))['animal']
        animal_time = animal_mat['time'][0][0][0]
        animal_time_diff = np.diff(animal_time)
        animal_time_kwargs = dict()
        if all(animal_time_diff == animal_time_diff[0]):
            animal_time_kwargs.update(rate=animal_time_diff[0], starting_time=animal_time[0])
        else:
            animal_time_kwargs.update(timestamps=H5DataIO(animal_time, compression="gzip"))

        # Processed (x,y,z) position
        pos_obj = Position(name="SubjectPosition")
        pos_obj.add_spatial_series(
            SpatialSeries(
                name='SpatialSeries',
                description="(x,y,z) coordinates tracking subject movement through the maze.",
                reference_frame="Unknown",
                # conversion=conversion,  # TODO: confirm this is in cm
                resolution=np.nan,
                data=H5DataIO(animal_mat['pos'][0][0], compression="gzip"),
                **animal_time_kwargs
            )
        )
        behavioral_processing_module.add(pos_obj)

        # Linearized position
        lin_pos_obj = Position(name="LinearizedPosition")
        lin_pos_obj.add_spatial_series(
            SpatialSeries(
                name='LinearizedSpatialSeries',
                description="Linearization of the (x,y,z) coordinates tracking subject movement through the maze.",
                reference_frame="Unknown",
                # conversion=conversion,  # TODO: confirm this is in cm
                resolution=np.nan,
                data=H5DataIO(animal_mat['pos_linearized'][0][0][0], compression="gzip"),
                **animal_time_kwargs
            )
        )
        behavioral_processing_module.add(lin_pos_obj)

        # Speed
        behavioral_processing_module.add(
            TimeSeries(
                name='SubjectSpeed',
                description="Instantaneous speed of subject through the maze.",
                unit="cm/s",  # TODO confirm cm
                # conversion=conversion,  # TODO: confirm this is in cm
                resolution=np.nan,
                data=H5DataIO(animal_mat['speed'][0][0][0], compression="gzip"),
                **animal_time_kwargs
            )
        )

        # Acceleration
        behavioral_processing_module.add(
            TimeSeries(
                name='Acceleration',
                description="Instantaneous acceleration of subject through the maze.",
                unit="cm/s^2",  # TODO confirm cm
                # conversion=conversion,  # TODO: confirm this is in cm
                resolution=np.nan,
                data=H5DataIO(animal_mat['acceleration'][0][0][0], compression="gzip"),
                **animal_time_kwargs
            )
        )

        # Temperature
        behavioral_processing_module.add(
            TimeSeries(
                name='Temperature',
                description="Internal brain temperature throughout the session.",
                unit="Celsius",
                resolution=np.nan,
                data=H5DataIO(animal_mat['temperature'][0][0][0], compression="gzip"),
                **animal_time_kwargs
            )
        )
