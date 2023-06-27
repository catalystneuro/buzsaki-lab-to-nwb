from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pynwb.file import NWBFile

from scipy.io import loadmat as loadmat_scipy
from hdmf.backends.hdf5.h5_utils import H5DataIO


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


def isNaN(num):
    return num != num


def to_direction(arr):
    output = []
    for value in arr:
        if isNaN(value):
            output.append("none")

        elif value == 0:
            output.append("right")

        else:
            output.append("left")

    return output


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

        familiar_final_idx = len(trial_info["trial_ints"])
        if len(trial_info["position_trcat"]) > 1:
            familiar_final_idx = len(trial_info["trial_ints"][0])

        data = []
        is_familiar_maze = []

        for idx, times in enumerate(trial_interval_list):
            data.append(
                dict(
                    start_time=float(times[0]),
                    stop_time=float(times[1]),
                )
            )

            is_familiar_maze.append(idx < familiar_final_idx)

        [nwbfile.add_trial(**row) for row in sorted(data, key=lambda x: x["start_time"])]

        visited_arm_data = to_direction(trial_info["visitedArm"])
        expected_arm_data = to_direction(trial_info["expectedArm"])

        nwbfile.add_trial_column(
            name="visited_matched_expected",
            description="A boolean (or NaN) representing whether the expected and visited arm of the trial matches",
            data=trial_info["choice"].astype("float8"),
        )

        nwbfile.add_trial_column(
            name="visited_arm",
            description="A string representing the visited arm of the trial",
            data=H5DataIO(visited_arm_data, compression="gzip"),
        )

        nwbfile.add_trial_column(
            name="expected_arm",
            description="A string representing the expected arm of the trial",
            data=H5DataIO(expected_arm_data, compression="gzip"),
        )

        nwbfile.add_trial_column(
            name="recordings",
            description="An integer value representing which recording this trial belongs to",
            data=trial_info["recordings"],
        )

        nwbfile.add_trial_column(
            name="is_familiar_maze",
            description="A boolean representing whether the maze is familiar or novel",
            data=is_familiar_maze,
        )
