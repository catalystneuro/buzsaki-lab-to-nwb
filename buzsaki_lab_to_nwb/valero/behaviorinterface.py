from pathlib import Path

import numpy as np
from pynwb.file import NWBFile, TimeIntervals, TimeSeries
from pynwb.behavior import SpatialSeries, Position, CompassDirection
from hdmf.backends.hdf5.h5_utils import H5DataIO

from neuroconv.utils.json_schema import FolderPathType
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module

from pymatreader import read_mat


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


# class HuzsarBehaviorSleepInterface(BaseDataInterface):
#     def __init__(self, folder_path: FolderPathType):
#         super().__init__(folder_path=folder_path)

#     def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
#         self.session_path = Path(self.source_data["folder_path"])
#         self.session_id = self.session_path.stem

#         module_name = "Neural states"
#         module_description = "Contains behavioral data concerning classified states."
#         processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)
#         # Sleep states
#         sleep_states_file_path = self.session_path / f"{self.session_id}.SleepState.states.mat"

#         assert sleep_states_file_path.exists(), f"Sleep states file not found: {sleep_states_file_path}"

#         mat_file = loadmat_scipy(sleep_states_file_path, simplify_cells=True)

#         state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
#         sleep_state_dic = mat_file["SleepState"]["ints"]
#         table = TimeIntervals(name="Sleep states", description="Sleep state of the animal.")
#         table.add_column(name="label", description="Sleep state.")

#         data = []
#         for sleep_state in state_label_names:
#             values = sleep_state_dic[sleep_state]
#             if len(values) != 0 and isinstance(values[0], int):
#                 values = [values]
#             for start_time, stop_time in values:
#                 data.append(
#                     dict(
#                         start_time=float(start_time),
#                         stop_time=float(stop_time),
#                         label=state_label_names[sleep_state],
#                     )
#                 )
#         [table.add_row(**row) for row in sorted(data, key=lambda x: x["start_time"])]
#         processing_module.add(table)
