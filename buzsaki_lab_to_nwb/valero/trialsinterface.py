from pathlib import Path

import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.file import NWBFile


class ValeroTrialInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        module_name = "sleep_states"
        module_description = "Contains classified states for sleep."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        # Sleep states
        behavioral_cellinfo_path = self.session_path / f"{self.session_id}.behavior.cellinfo.mat"
        assert behavioral_cellinfo_path.exists(), f"Sleep states file not found: {behavioral_cellinfo_path}"

        mat_file = read_mat(behavioral_cellinfo_path)
        trial_data = mat_file["behavior"]["trials"]
        trial_intervals = trial_data["startPoint"]
        # start_time, stop_time = trial_intervals[:, 0], trial_intervals[:, 1]
        visted_arm_array = trial_data["visitedArm"]

        nwbfile.add_trial_column(
            name="visited_arm",
            description="Which side of the linear track was visited",
        )

        for time_interval, visited_arm in zip(trial_intervals, visted_arm_array):
            start_time = time_interval[0]
            stop_time = time_interval[1]
            nwbfile.add_trial(
                start_time=start_time,
                stop_time=stop_time,
                visited_arm=visited_arm,
            )
