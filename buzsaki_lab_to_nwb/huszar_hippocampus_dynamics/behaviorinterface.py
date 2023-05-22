from pathlib import Path

import numpy as np
from pynwb.file import NWBFile, TimeIntervals, TimeSeries
from pynwb.behavior import SpatialSeries, Position, CompassDirection
from hdmf.backends.hdf5.h5_utils import H5DataIO

from neuroconv.utils.json_schema import FolderPathType
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module

from scipy.io import loadmat as loadmat_scipy


class HuzsarBehaviorSleepInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        module_name = "Neural states"
        module_description = "Contains behavioral data concerning classified states."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)
        # Sleep states
        sleep_states_file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"

        assert sleep_states_file_path.exists(), f"Sleep states file not found: {sleep_states_file_path}"

        mat_file = loadmat_scipy(sleep_states_file_path, simplify_cells=True)

        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        sleep_state_dic = mat_file["SleepState"]["ints"]
        table = TimeIntervals(name="Sleep states", description="Sleep state of the animal.")
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

        # Add trial table from the behavior file
        behavior_file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        behavior_mat = loadmat_scipy(behavior_file_path, simplify_cells=True)

        trial_info = behavior_mat["behavior"]["trials"]
        trial_interval_list = trial_info['trial_ints']

        data = []

        for start_time, stop_time in trial_interval_list:
            data.append(
                dict(
                    start_time=float(start_time),
                    stop_time=float(stop_time),
                )
            )
        [nwbfile.add_trial(**row) for row in sorted(data, key=lambda x: x["start_time"])]

        nwbfile.add_trial_column(name="choice", description="choice of the trial", data=trial_info['choice'])
        nwbfile.add_trial_column(name="visited_arm", description="visited arm of the trial", data=trial_info['visitedArm'])
        nwbfile.add_trial_column(name="expected_arm", description="expected arm of the trial", data=trial_info['expectedArm'])
        nwbfile.add_trial_column(name="recordings", description="recordings of the trial", data=trial_info['recordings'])
        # nwbfile.add_trial_column(name="start_point", description="start point of the trial", data=trial_info['startPoint'])
        # nwbfile.add_trial_column(name="end_delay", description="end delay of the trial", data=trial_info['endDelay'])

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

        module_name = "Figure - 8 maze"
        module_description = "Figure 8 - maze"
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        mat_file = loadmat_scipy(file_path, simplify_cells=True)

        timestamps = mat_file["behavior"]["timestamps"]
        position = mat_file["behavior"]["position"]
        lin = position["lin"]
        x = position["x"]
        y = position["y"]
        data = np.column_stack((x, y))

        unit = "cm"
        conversion = 100.0  # cm to m TODO: Double check if this is the meaning.
        reference_frame = "TBD"
        description = mat_file["behavior"]["description"]

        if isinstance(description, np.ndarray):
            description = description[0] # NOTE: Not sure this is the appropriate way to handle this, but this case shows up in e13_26m1_211019
        
        pos_obj = Position(name=description)
        spatial_series_object = SpatialSeries(
            name="position",
            description="(x,y) coordinates tracking subject movement.",
            data=H5DataIO(data, compression="gzip"),
            reference_frame=reference_frame,
            unit=unit,
            conversion=conversion,
            timestamps=timestamps,
            resolution=np.nan,
        )
        pos_obj.add_spatial_series(spatial_series_object)
        processing_module.add_data_interface(pos_obj)

        time_series = TimeSeries(
            name="linearized_position", data=lin, unit=unit, timestamps=timestamps, resolution=np.nan
        )
        processing_module.add_data_interface(time_series)

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
