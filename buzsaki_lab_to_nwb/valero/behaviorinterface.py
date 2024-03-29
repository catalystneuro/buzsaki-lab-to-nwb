import json
import warnings
from pathlib import Path

import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO
from ndx_events import LabeledEvents
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.behavior import Position, SpatialSeries
from pynwb.file import NWBFile, TimeIntervals, TimeSeries


class ValeroBehaviorLinearTrackRewardsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        if not file_path.is_file():
            warnings.warn(f"Behavior file not found: {file_path}. Skipping rewards interface. \n")
            return nwbfile

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
            name="RewardEventsLinearTrack",
            description="rewards in the linear track",
            timestamps=timestamps,
            data=data,
            labels=["right_reward", "left_reward"],
        )

        # Create behavior module
        behavior_description = "Tracking data obtained from positional tracking in video"
        processing_module = get_module(nwbfile=nwbfile, name="behavior", description=behavior_description)

        processing_module.add(events)


class ValeroBehaviorLinearTrackInterface(BaseDataInterface):
    """Behavior interface"""

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        if file_path.is_file():
            mat_file = read_mat(file_path)
            behavior_data = mat_file["behavior"]
            timestamps = behavior_data["timestamps"]
            position = behavior_data["position"]
        else:
            warnings.warn(f"\n Behavior file {file_path} not found. Trying `Tracking.Behavior.mat` file instead \n")
            file_path = self.session_path / f"{self.session_id}.Tracking.Behavior.mat"

            mat_file = read_mat(file_path)
            tracking_data = mat_file["tracking"]
            position = tracking_data["position"]
            timestamps = tracking_data["timestamps"]

            if not file_path.is_file():
                warnings.warn(f" \n Tracking behavior file {file_path} not found. Skipping behavior interface \n")
                return nwbfile

        x = position["x"]
        y = position["y"]
        data = np.column_stack((x, y))

        unit = "cm"
        conversion = 100.0  # cm to m
        reference_frame = "Arbitrary, camera"
        position_container = Position(name="LinearMazePositionTracking")

        spatial_series_xy = SpatialSeries(
            name="SpatialSeriesRaw",
            description="(x,y) coordinates tracking subject movement from above with camera on a PVC linear track (110 cm long, 6.35 cm wide)",
            data=H5DataIO(data=data, compression="gzip"),
            reference_frame=reference_frame,
            unit=unit,
            timestamps=timestamps,
            resolution=np.nan,
        )

        position_container.add_spatial_series(spatial_series_xy)

        if "lin" in position:
            lin = position["lin"]
            spatial_series_linear = SpatialSeries(
                name="SpatiaLSeriesLinearized",
                description="Linearized position of the subject on the track.",
                data=H5DataIO(data=lin, compression="gzip"),
                unit=unit,
                timestamps=timestamps,
                conversion=conversion,
                resolution=np.nan,
                reference_frame=reference_frame,
            )
            position_container.add_spatial_series(spatial_series_linear)

        # Create behavior module
        behavior_description = "Tracking data obtained from positional tracking in video"
        processing_module = get_module(nwbfile=nwbfile, name="behavior", description=behavior_description)
        processing_module.add_data_interface(position_container)
