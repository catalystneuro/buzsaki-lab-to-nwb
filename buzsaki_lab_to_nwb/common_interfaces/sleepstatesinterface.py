"""Authors: Heberto Mayorquin and Cody Baker."""
from pathlib import Path

from scipy.io import loadmat
from pynwb import NWBFile
from pynwb.file import TimeIntervals
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils import FilePathType
from nwb_conversion_tools.tools.nwb_helpers import get_module


class SleepStatesInterface(BaseDataInterface):
    """Data interface for handling sleepStates.mat files found across multiple projects."""

    def __init__(self, mat_file_path: FilePathType):
        super().__init__(mat_file_path=mat_file_path)

    def run_conversion(self, nwbfile: NWBFile, metadata, ecephys_start_time: float = 0.0):
        processing_module = get_module(
            nwbfile=nwbfile, name="behavior", description="Contains behavioral data concerning classified states."
        )

        if Path(self.source_data["mat_file_path"]).exists():
            mat_file = loadmat(file_name=self.source_data["mat_file_path"])

            sleep_state_dic = mat_file["SleepState"]["ints"][0][0]
            state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM", MAstate="MA")
            table = TimeIntervals(name="sleep_states", description="Sleep state of the animal.")
            table.add_column(name="label", description="Sleep state.")

            data = []
            for sleep_state in set(mat_file["SleepState"]["ints"][0][0].dtype.names):
                values = sleep_state_dic[sleep_state][0][0]
                if len(values) != 0 and isinstance(values[0], int):
                    values = [values]
                for start_time, stop_time in values:
                    data.append(
                        dict(
                            start_time=ecephys_start_time + float(start_time),
                            stop_time=ecephys_start_time + float(stop_time),
                            label=state_label_names[sleep_state],
                        )
                    )
            [table.add_row(**row) for row in sorted(data, key=lambda x: x["start_time"])]
            processing_module.add(table)
