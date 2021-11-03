"""Authors: Heberto Mayorquin and Cody Baker."""
from pathlib import Path
from nwb_conversion_tools.utils.json_schema import FolderPathType

from pynwb.file import NWBFile, TimeIntervals
from mat73 import loadmat as loadmat_mat73
from mat4py import loadmat as loadmat_mat4py
from scipy.io import loadmat as loadmat_scipy

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils.conversion_tools import get_module


def read_matlab_file(file_path):
    file_path = str(file_path)

    try:
        mat_file = loadmat_mat4py(str(file_path))
        mat_file["read"] = "mat4py"
    except:
        try:
            mat_file = loadmat_mat73(file_path)
            mat_file["read"] = "mat73"
        except:
            mat_file = loadmat_scipy(file_path)
            mat_file["read"] = "scipy"
    return mat_file


class YutaVCBehaviorInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict):
        session_path = Path(self.source_data["folder_path"])

        module_name = "Neural states"
        module_description = "Contains behavioral data concerning classified states."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        # Sleep states
        sleep_file_path = session_path / f"{session_path.stem}.SleepState.states.mat"
        mat_file = read_matlab_file(sleep_file_path)

        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM", MAstate="MA")
        sleep_state_dic = mat_file["SleepState"]["ints"]
        table = TimeIntervals(name="Sleep states", description="Sleep state of the animal.")
        table.add_column(name="label", description="Sleep state.")

        data = []
        for sleep_state in state_label_names:
            values = sleep_state_dic[sleep_state]
            for start_time, stop_time in values:
                data.append(
                    dict(start_time=float(start_time), stop_time=float(stop_time), label=state_label_names[sleep_state])
                )
        [table.add_row(**row) for row in sorted(data, key=lambda x: x["start_time"])]
        processing_module.add(table)

        # Up and down states
        behavioral_file_path = session_path / f"{session_path.stem}.SlowWaves.events.mat"
        behavioral_file = read_matlab_file(behavioral_file_path)
        table = TimeIntervals(name="Up-Down states", description="Up and down states classified by LFP.")
        table.add_column(name="label", description="state.")

        data = []
        up_and_down_intervals_dic = behavioral_file["SlowWaves"]["ints"]
        for state, values in up_and_down_intervals_dic.items():
            for start_time, stop_time in values:
                data.append(dict(start_time=float(start_time), stop_time=float(stop_time), label=state))
        [table.add_row(**row) for row in sorted(data, key=lambda x: x["start_time"])]
        processing_module.add(table)
