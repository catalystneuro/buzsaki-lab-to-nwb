import warnings
from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.file import NWBFile


class ValeroTrialInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        # We use the behavioral cellinfo file to get the trial intervals
        behavioral_cellinfo_path = self.session_path / f"{self.session_id}.behavior.cellinfo.mat"
        if not behavioral_cellinfo_path.exists():
            warnings.warn(f"Behavioral cell info file not found: {behavioral_cellinfo_path}")
            return nwbfile

        mat_file = read_mat(behavioral_cellinfo_path)
        trial_data = mat_file["behavior"]["trials"]
        trial_intervals = trial_data["startPoint"]
        visted_arm_array = trial_data["visitedArm"]

        nwbfile.add_trial_column(
            name="visited_arm",
            description="Which side of the linear track was visited",
        )

        for time_interval, visited_arm in zip(trial_intervals, visted_arm_array):
            start_time, stop_time = time_interval
            nwbfile.add_trial(start_time=start_time, stop_time=stop_time, visited_arm=visited_arm)
