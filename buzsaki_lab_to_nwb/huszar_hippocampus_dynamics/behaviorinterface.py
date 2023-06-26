from pathlib import Path

import numpy as np
from pynwb.file import NWBFile, TimeIntervals, TimeSeries
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

from neuroconv.utils.json_schema import FolderPathType
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module

from scipy.io import loadmat as loadmat_scipy
from pymatreader import read_mat

from ndx_events import LabeledEvents


class HuszarBehavior8MazeRewardsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        mat_file = read_mat(file_path)

        events_data = mat_file["behavior"]["events"]

        # Extract timestamps and create labels for rewards
        reward_r_timestamps = events_data["rReward"]
        reward_l_timestamps = events_data["lReward"]
        label_reward_r = np.ones(reward_r_timestamps.shape[0], dtype=int)
        label_reward_l = np.zeros(reward_l_timestamps.shape[0], dtype=int)

        # Create a structure to concatenate timestamps and sort by them
        reward_r = np.vstack((reward_r_timestamps, label_reward_r))
        reward_l = np.vstack((reward_l_timestamps, label_reward_l))
        rewards = np.concatenate((reward_r, reward_l), axis=1)

        timestamps_both_rewards = rewards[0, :]
        rewards = rewards[:, timestamps_both_rewards.argsort()]

        timestamps = rewards[0, :]
        data = rewards[1, :].astype("int8")

        assert np.all(np.diff(timestamps) > 0)

        events = LabeledEvents(
            name="RewardEventsEightMazeTrack",
            description="Rewards in a figure-eight maze",
            timestamps=timestamps,
            data=data,
            labels=["right_reward", "left_reward"],
        )

        processing_module = get_module(nwbfile=nwbfile, name="behavior")

        processing_module.add(events)


class HuzsarBehaviorSleepInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        processing_module = get_module(nwbfile=nwbfile, name="behavior")

        # Sleep states
        sleep_states_file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"

        assert sleep_states_file_path.exists(), f"Sleep states file not found: {sleep_states_file_path}"

        mat_file = loadmat_scipy(sleep_states_file_path, simplify_cells=True)

        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        sleep_state_dic = mat_file["SleepState"]["ints"]
        table = TimeIntervals(name="SleepStates", description="Sleep state of the animal.")
        table.add_column(name="label", description="Sleep state.")

        data = []
        for sleep_state in state_label_names:
            values = sleep_state_dic[sleep_state]
            if len(values) != 0 and isinstance(values[0], int):
                values = [values]
            for start_time, stop_time in values:
                data.append(
                    dict(
                        start_time=float(start_time),
                        stop_time=float(stop_time),
                        label=state_label_names[sleep_state],
                    )
                )
        [table.add_row(**row) for row in sorted(data, key=lambda x: x["start_time"])]
        processing_module.add(table)

    def align_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def get_timestamps(self) -> np.ndarray:
        """
        Retrieve the timestamps for the data in this interface.

        Returns
        -------
        timestamps: numpy.ndarray
            The timestamps for the data stream.
        """
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def get_original_timestamps(self) -> np.ndarray:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps: numpy.ndarray
            The timestamps for the data stream.
        """
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )


class HuszarBehavior8MazeInterface(BaseDataInterface):
    """Behavior interface"""

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        mat_file = loadmat_scipy(file_path, simplify_cells=True)

        timestamps = mat_file["behavior"]["timestamps"]
        position = mat_file["behavior"]["position"]
        lin = position["lin"]
        x = position["x"]
        y = position["y"]
        data = np.column_stack((x, y))

        unit = "cm"
        reference_frame = "Arbitrary, camera"

        nest_depth = len(mat_file["behavior"]["trials"]["position_trcat"])

        # Merge unique descriptions if there are nested entries inside the behavior file
        merged_behavior_descriptions = mat_file["behavior"]["description"]

        if nest_depth > 1:
            merged_behavior_descriptions = ", ".join(
                mat_file["behavior"]["description"]
            )  # NOTE: Description is an array in this case

        complete_behavior_description = (
            f"The behavior of the subject for the following recordings: {merged_behavior_descriptions}"
        )
        processing_module = get_module(nwbfile=nwbfile, name="behavior", description=complete_behavior_description)

        pos_obj = Position(
            name="SubjectPosition",
        )

        spatial_series_object = SpatialSeries(
            name="SpatialSeries",
            description="(x,y) coordinates tracking subject movement.",
            data=H5DataIO(data, compression="gzip"),
            reference_frame=reference_frame,
            unit=unit,
            timestamps=timestamps,
            resolution=np.nan,
        )

        pos_obj.add_spatial_series(spatial_series_object)
        processing_module.add(pos_obj)

        # Add linearized information
        linearized_pos_obj = Position(
            name="LinearizedPosition",
        )

        linearized_spatial_series_object = SpatialSeries(
            name="LinearizedSpatialSeries",
            description="Linearization of the (x,y) coordinates tracking subject movement.",
            data=H5DataIO(lin, compression="gzip"),
            unit=unit,
            reference_frame=reference_frame,
            timestamps=timestamps,
            resolution=np.nan,
        )

        linearized_pos_obj.add_spatial_series(linearized_spatial_series_object)

        processing_module.add(linearized_pos_obj)

    def align_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def get_timestamps(self) -> np.ndarray:
        """
        Retrieve the timestamps for the data in this interface.

        Returns
        -------
        timestamps: numpy.ndarray
            The timestamps for the data stream.
        """
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def get_original_timestamps(self) -> np.ndarray:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps: numpy.ndarray
            The timestamps for the data stream.
        """
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )
