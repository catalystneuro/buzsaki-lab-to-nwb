from pathlib import Path

import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.behavior import Position, SpatialSeries
from pynwb.file import NWBFile, TimeIntervals, TimeSeries


class ValeroBehaviorLinearTrackInterface(BaseDataInterface):
    """Behavior interface"""

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        mat_file = read_mat(file_path)
        behavior_data = mat_file["behavior"]
        module_name = behavior_data["description"]
        description = "PVC linear track (110 cm long, 6.35 cm wide)"

        module_description = description
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        timestamps = behavior_data["timestamps"]
        position = behavior_data["position"]
        lin = position["lin"]
        x = position["x"]
        y = position["y"]
        data = np.column_stack((x, y))

        unit = "cm"
        conversion = 100.0  # cm to m
        reference_frame = "Arbitrary, camera"
        position_container = Position(name="position_tracking")

        spatial_series_xy = SpatialSeries(
            name="spatial_position",
            description="(x,y) coordinates tracking subject movement from above with camera",
            data=H5DataIO(data=data, compression="gzip"),
            reference_frame=reference_frame,
            unit=unit,
            conversion=conversion,
            timestamps=timestamps,
            resolution=np.nan,
        )

        position_container.add_spatial_series(spatial_series_xy)

        spatial_series_linear = SpatialSeries(
            name="linearized_position",
            data=H5DataIO(data=lin, compression="gzip"),
            unit=unit,
            timestamps=timestamps,
            conversion=conversion,
            resolution=np.nan,
            reference_frame=reference_frame,
        )

        position_container.add_spatial_series(spatial_series_linear)
        processing_module.add_data_interface(position_container)


class ValeroBehaviorSleepStatesInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        module_name = "sleep_states"
        module_description = "Contains classified states for sleep."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        # Sleep states
        sleep_states_file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"

        assert sleep_states_file_path.exists(), f"Sleep states file not found: {sleep_states_file_path}"

        mat_file = read_mat(sleep_states_file_path)

        sleep_intervals = mat_file["SleepState"]["ints"]
        available_states = [str(key) for key in sleep_intervals.keys()]

        table = TimeIntervals(name="Sleep states", description="Sleep state of the animal.")
        table.add_column(name="label", description="Sleep state.")

        table_rows = []
        for state_name, state_intervals in sleep_intervals.items():
            for start_time, stop_time in state_intervals:
                row_as_dict = dict(start_time=float(start_time), stop_time=float(stop_time), label=state_name)
                table_rows.append(row_as_dict)

        [table.add_row(**row_as_dict) for row_as_dict in sorted(table_rows, key=lambda x: x["start_time"])]
        processing_module.add(table)
