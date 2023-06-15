from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pynwb.file import NWBFile

from scipy.io import loadmat as loadmat_scipy


def access_behavior_property_safe(property, parent, behavior_mat):
    trial_info = behavior_mat["behavior"]["trials"]
    nest_depth = len(trial_info["position_trcat"])

    value = parent[property]
    if nest_depth > 1:
        value = [num for sublist in value for num in sublist]  # Flatten the list if large depth

    assert len(value) == len(
        trial_info["recordings"]
    )  # Save access properties should have the same length as the number of recordings

    return value


# Add trial table from the behavior file
class HuszarTrialsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        # Add trial table from the behavior file
        behavior_file_path = self.session_path / f"{self.session_id}.Behavior.mat"
        behavior_mat = loadmat_scipy(behavior_file_path, simplify_cells=True)

        trial_info = behavior_mat["behavior"]["trials"]
        trial_interval_list = access_behavior_property_safe("trial_ints", trial_info, behavior_mat)

        data = []

        for start_time, stop_time in trial_interval_list:
            data.append(
                dict(
                    start_time=float(start_time),
                    stop_time=float(stop_time),
                )
            )

        [nwbfile.add_trial(**row) for row in sorted(data, key=lambda x: x["start_time"])]

        nwbfile.add_trial_column(
            name="choice",
            description="An value of 0 or 1 representing whether the expected and visited arm of the trial matches",
            data=trial_info["choice"],
        )
        nwbfile.add_trial_column(
            name="visited_arm",
            description="An integer value representing the visited arm of the trial",
            data=trial_info["visitedArm"],
        )
        nwbfile.add_trial_column(
            name="expected_arm",
            description="An integer value representing the expected arm of the trial",
            data=trial_info["expectedArm"],
        )
        nwbfile.add_trial_column(
            name="recordings",
            description="An integer value representing which recording this trial belongs to",
            data=trial_info["recordings"],
        )
        # nwbfile.add_trial_column(name="start_point", description="start point of the trial", data=trial_info['startPoint'])
        # nwbfile.add_trial_column(name="end_delay", description="end delay of the trial", data=trial_info['endDelay'])
