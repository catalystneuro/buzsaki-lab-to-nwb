"""Authors: Heberto Mayorquin and Cody Baker."""
from pathlib import Path
import warnings

import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO

from pynwb.file import NWBFile, TimeIntervals
from pynwb.behavior import SpatialSeries, Position, CompassDirection
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils.conversion_tools import get_module
from nwb_conversion_tools.utils.json_schema import FolderPathType
from spikeextractors import NeuroscopeRecordingExtractor

from .tingleyseptal_utils import read_matlab_file


class TingleySeptalBehaviorInterface(BaseDataInterface):
    """Behavior data interface for the Tingley Septal project."""

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict):
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem

        # Load the file with behavioral data
        behavior_file_path = Path(session_path) / f"{session_id}.behavior.mat"
        behavior_mat = read_matlab_file(str(behavior_file_path))["behavior"]

        # Add trials
        events = behavior_mat["events"]
        trial_interval_list = events["trialIntervals"]

        data = []
        for start_time, stop_time in trial_interval_list:
            data.append(
                dict(
                    start_time=float(start_time),
                    stop_time=float(stop_time),
                )
            )
        [nwbfile.add_trial(**row) for row in sorted(data, key=lambda x: x["start_time"])]

        trial_list = events["trials"]
        direction_list = [trial.get("direction", "") for trial in trial_list]
        trial_type_list = [trial.get("type", "") for trial in trial_list]

        if not all([direction == "" for direction in direction_list]):
            nwbfile.add_trial_column(name="direction", description="direction of the trial", data=direction_list)

        if not all([trial_type == "" for trial_type in trial_type_list]):
            nwbfile.add_trial_column(name="trial_type", description="type of trial", data=trial_type_list)

        # Position
        module_name = "behavior"
        module_description = "Contains behavioral data concerning position."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        timestamps = np.array(behavior_mat["timestamps"])[..., 0]

        position = behavior_mat["position"]
        pos_data = [[x, y, z] for (x, y, z) in zip(position["x"], position["y"], position["y"])]
        pos_data = np.array(pos_data)[..., 0]

        unit = behavior_mat.get("units", "")

        if unit == ["m", "meter", "meters"]:
            conversion = 1.0
        else:
            warnings.warn(f"Spatial units {unit} not listed in meters; " "setting conversion to nan.")
            conversion = np.nan

        description = behavior_mat.get("description", "generic_position_tracking").replace("/", "-")
        rotation_type = behavior_mat.get("rotationType", "non_specified")

        pos_obj = Position(name=f"{description}_task".replace(" ", "_"))

        spatial_series_object = SpatialSeries(
            name="position",
            description="(x,y,z) coordinates tracking subject movement.",
            data=H5DataIO(pos_data, compression="gzip"),
            reference_frame="unknown",
            unit=unit,
            conversion=conversion,
            timestamps=timestamps,
            resolution=np.nan,
        )

        pos_obj.add_spatial_series(spatial_series_object)

        # Add error if available
        errorPerMarker = behavior_mat.get("errorPerMarker", None)
        if errorPerMarker:
            error_data = np.array([error for error in errorPerMarker])[..., 0]

            spatial_series_object = SpatialSeries(
                name="error_per_marker",
                description="Estimated error for marker tracking from optitrack system.",
                data=H5DataIO(error_data, compression="gzip"),
                reference_frame="unknown",
                conversion=conversion,
                timestamps=timestamps,
                resolution=np.nan,
            )
            pos_obj.add_spatial_series(spatial_series_object)

        processing_module.add_data_interface(pos_obj)

        # Compass
        try:
            orientation = behavior_mat["orientation"]
            orientation_data = [
                [x, y, z, w]
                for (x, y, z, w) in zip(orientation["x"], orientation["y"], orientation["z"], orientation["w"])
            ]
            orientation_data = np.array(orientation_data)[..., 0]

            compass_obj = CompassDirection(name=f"allocentric_frame_tracking")

            spatial_series_object = SpatialSeries(
                name="orientation",
                description=f"(x, y, z, w) orientation coordinates, orientation type: {rotation_type}",
                data=H5DataIO(orientation_data, compression="gzip"),
                reference_frame="unknown",
                conversion=conversion,
                timestamps=timestamps,
                resolution=np.nan,
            )
            compass_obj.add_spatial_series(spatial_series_object)
            processing_module.add_data_interface(compass_obj)

        except KeyError:
            warnings.warn(f"Orientation data not found")

        # States
        module_name = "ecephys"
        module_description = "Contains behavioral data concerning classified states."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        # Sleep states
        sleep_file_path = session_path / f"{session_id}.SleepState.states.mat"
        if Path(sleep_file_path).exists():
            mat_file = read_matlab_file(sleep_file_path)

            state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM", MAstate="MA")
            sleep_state_dic = mat_file["SleepState"]["ints"]
            table = TimeIntervals(name="sleep_states", description="Sleep state of the animal.")
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

        # Add epochs
        lfp_file_path = session_path / f"{session_path.name}.lfp"
        raw_file_path = session_path / f"{session_id}.dat"
        if raw_file_path.is_file():
            recorder = NeuroscopeRecordingExtractor(file_path=raw_file_path)
        else:
            recorder = NeuroscopeRecordingExtractor(file_path=lfp_file_path)

        num_frames = recorder.get_num_frames()
        sampling_frequency = recorder.get_sampling_frequency()
        end_of_the_session = num_frames / sampling_frequency

        session_start = 0.0
        start_trials_time = min([interval[0] for interval in trial_interval_list])
        end_trials_time = max([interval[1] for interval in trial_interval_list])
        end_of_the_session = end_of_the_session

        nwbfile.add_epoch(start_time=session_start, stop_time=start_trials_time, tags="before trials")
        nwbfile.add_epoch(start_time=start_trials_time, stop_time=end_trials_time, tags="during trials")
        nwbfile.add_epoch(start_time=end_trials_time, stop_time=end_of_the_session, tags="after trials")
