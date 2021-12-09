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

from .tingleyseptal_utils import read_matlab_file


class TingleySeptalBehaviorInterface(BaseDataInterface):
    """Behavior data interface for the Tingley Septal project."""

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict):
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem

        # Position
        module_name = "Position"
        module_description = "Contains behavioral data concerning position."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        behavior_file_path = Path(session_path) / f"{session_id}.behavior.mat"

        behavior_mat = read_matlab_file(str(behavior_file_path))["behavior"]
        time_stamps = behavior_mat["timestamps"]
        starting_time = time_stamps[0][0]
        rate = behavior_mat["samplingRate"]

        position = behavior_mat["position"]
        pos_data = [[x, y, z] for (x, y, z) in zip(position["x"], position["y"], position["y"])]
        pos_data = np.array(pos_data)[:, :, 0]

        units = behavior_mat.get("units", None)
        if units == "m":
            conversion = 1.0
        else:
            warnings.warn(f"Spatial units {units} not listed in meters; " "setting conversion to nan.")
            conversion = np.nan

        description = behavior_mat.get("description", "generic_position_tracking").replace("/", "-")
        rotation_type = behavior_mat.get("rotationType", "non_specified")

        pos_obj = Position(name=f"{description}")

        spatial_series_object = SpatialSeries(
            name=f"Position",
            description=f"(x,y,z) coordinates tracking subject movement through",
            data=H5DataIO(pos_data, compression="gzip"),
            reference_frame="unknown",
            conversion=conversion,
            starting_time=starting_time,
            rate=float(rate),
            resolution=np.nan,
        )
        
        # When available add the error to this module
        
        pos_obj.add_spatial_series(spatial_series_object)

        # Compass 
        module_name = "Orientation"
        module_description = "Contains behavioral data concerning orientation."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)
          
        compass_obj = CompassDirection(name=f"route centric")

        try:
            orientation = behavior_mat["orientation"]
            orientation_data = [
                [x, y, z, w]
                for (x, y, z, w) in zip(orientation["x"], orientation["y"], orientation["z"], orientation["w"])
            ]
            orientation_data = np.array(orientation_data)[..., 0]

            spatial_series_object = SpatialSeries(
                name=f"Orientation",
                description=f"(x, y, z, w) orientation coordinates, orientation type: {rotation_type}",
                data=H5DataIO(pos_data, compression="gzip"),
                reference_frame="unknown",
                conversion=conversion,
                starting_time=starting_time,
                rate=float(rate),
                resolution=np.nan,
            )
            compass_obj.add_spatial_series(spatial_series_object)
        except KeyError:
            warnings.warn(f"Orientation data not found")

        processing_module.add_data_interface(compass_obj)

        # States
        module_name = "Neural states"
        module_description = "Contains behavioral data concerning classified states."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        # Sleep states
        sleep_file_path = session_path / f"{session_id}.SleepState.states.mat"
        if Path(sleep_file_path).exists():
            mat_file = read_matlab_file(sleep_file_path)

            state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM", MAstate="MA")
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
