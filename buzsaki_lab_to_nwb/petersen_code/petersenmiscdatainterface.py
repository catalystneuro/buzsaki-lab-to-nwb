"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
from pathlib import Path
from hdf5storage import loadmat  # scipy.io loadmat doesn't support >= v7.3 matlab files
import pandas as pd

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils.conversion_tools import check_regular_timestamps, get_module
from pynwb import NWBFile, TimeSeries
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

# TODO for future draft - Add acquisition of raw position from Take files (meters) or Optitrack (cm)
# Use edges of trials.state time series to define pre-cooling, cooling, and post-cooling epochs
# Include eeg & ripple data
# Add various raw acquisition sources with metadata from intan rhd file
# Not all foldesr had an animal.mat file for pos info
# Fix issues with duplicate Take files in some sessions


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
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.name

        # Trials
        take_file_paths = [x for x in session_path.iterdir() if "Take" in x.name]
        # Some sessions had duplicate/non-corresponding Take files
        if len(take_file_paths) == 1:
            take_file_path = take_file_paths[0]
            take_file = pd.read_csv(take_file_path, header=5)
            take_file_time_name = [x for x in take_file if "Time" in x][
                0
            ]  # Can be either 'Time' or 'Time (Seconds)'
            take_frame_to_time = {
                x: y for x, y in zip(take_file["Frame"], take_file[take_file_time_name])
            }

            trial_info = loadmat(
                str(session_path / f"{session_id}.trials.behavior.mat")
            )["trials"]
            trial_start_frames = trial_info["start"][0][0]
            n_trials = len(trial_start_frames)
            trial_end_frames = trial_info["end"][0][0]
            trial_stat = trial_info["stat"][0][0]
            trial_stat_labels = [x[0][0] for x in trial_info["labels"][0][0]]
            cooling_info = trial_info["cooling"][0][0]
            cooling_map = dict(
                {0: "Cooling off", 1: "Pre-Cooling", 2: "Cooling on", 3: "Post-Cooling"}
            )
            trial_error = trial_info["error"][0][0]
            error_trials = np.array([False] * n_trials)
            error_trials[
                np.array(trial_error).astype(int) - 1
            ] = True  # -1 from Matlab indexing

            trial_starts = []
            trial_ends = []
            trial_condition = []
            for k in range(n_trials):
                trial_starts.append(take_frame_to_time[trial_start_frames[k]])
                trial_ends.append(take_frame_to_time[trial_end_frames[k]])
                nwbfile.add_trial(start_time=trial_starts[k], stop_time=trial_ends[k])
                trial_condition.append(trial_stat_labels[int(trial_stat[k]) - 1])

            nwbfile.add_trial_column(
                name="condition",
                description="Whether the maze condition was left or right.",
                data=trial_condition,
            )
            nwbfile.add_trial_column(
                name="error",
                description="Whether the subject made a mistake.",
                data=error_trials,
            )

            if (
                "temperature" in trial_info
            ):  # Some sessions don't have this for some reason
                trial_temperature = trial_info["temperature"][0][0]
                nwbfile.add_trial_column(
                    name="temperature",
                    description="Average brain temperature for the trial.",
                    data=trial_temperature,
                )

            if (
                len(cooling_info) == n_trials
            ):  # some sessions had incomplete cooling info
                trial_cooling = [
                    cooling_map[int(cooling_info[k])] for k in range(n_trials)
                ]
                nwbfile.add_trial_column(
                    name="cooling state",
                    description="The labeled cooling state of the subject during the trial.",
                    data=trial_cooling,
                )

        # Position
        animal_file_path = session_path / "animal.mat"

        if animal_file_path.is_file():
            behavioral_processing_module = get_module(
                nwbfile, "behavior", "Contains processed behavioral data."
            )

            animal_mat = loadmat(str(animal_file_path))["animal"]
            animal_time = animal_mat["time"][0][0][0]
            animal_time_kwargs = dict()
            if check_regular_timestamps(animal_time):
                animal_time_kwargs.update(
                    rate=animal_time[1] - animal_time[0], starting_time=animal_time[0]
                )
            else:
                animal_time_kwargs.update(
                    timestamps=H5DataIO(animal_time, compression="gzip")
                )

            # Processed (x,y,z) position
            pos_obj = Position(name="SubjectPosition")
            pos_obj.add_spatial_series(
                SpatialSeries(
                    name="SpatialSeries",
                    description="(x,y,z) coordinates tracking subject movement through the maze.",
                    reference_frame="Unknown",
                    conversion=1e-2,
                    resolution=np.nan,
                    data=H5DataIO(
                        np.array(animal_mat["pos"][0][0]).T, compression="gzip"
                    ),
                    **animal_time_kwargs,
                )
            )
            behavioral_processing_module.add(pos_obj)

            # Linearized position
            if (
                "pos_linearized" in animal_mat
            ):  # Some sessions don't have this for some reason
                lin_pos_obj = Position(name="LinearizedPosition")
                lin_pos_obj.add_spatial_series(
                    SpatialSeries(
                        name="LinearizedSpatialSeries",
                        description="Linearization of the (x,y,z) coordinates tracking subject movement through maze.",
                        reference_frame="Unknown",
                        conversion=1e-2,
                        resolution=np.nan,
                        data=H5DataIO(
                            animal_mat["pos_linearized"][0][0][0], compression="gzip"
                        ),
                        **animal_time_kwargs,
                    )
                )
                behavioral_processing_module.add(lin_pos_obj)

            # Speed
            behavioral_processing_module.add(
                TimeSeries(
                    name="SubjectSpeed",
                    description="Instantaneous speed of subject through the maze.",
                    unit="cm/s",
                    resolution=np.nan,
                    data=H5DataIO(animal_mat["speed"][0][0][0], compression="gzip"),
                    **animal_time_kwargs,
                )
            )

            # Acceleration
            behavioral_processing_module.add(
                TimeSeries(
                    name="Acceleration",
                    description="Instantaneous acceleration of subject through the maze.",
                    unit="cm/s^2",
                    resolution=np.nan,
                    data=H5DataIO(
                        animal_mat["acceleration"][0][0][0], compression="gzip"
                    ),
                    **animal_time_kwargs,
                )
            )

            # Temperature
            behavioral_processing_module.add(
                TimeSeries(
                    name="Temperature",
                    description="Internal brain temperature throughout the session.",
                    unit="Celsius",
                    resolution=np.nan,
                    data=H5DataIO(
                        animal_mat["temperature"][0][0][0], compression="gzip"
                    ),
                    **animal_time_kwargs,
                )
            )
