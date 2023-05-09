from pathlib import Path

import numpy as np
from pynwb.file import NWBFile, TimeIntervals


from neuroconv.utils.json_schema import FolderPathType
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module

from scipy.io import loadmat as loadmat_scipy

class HuzsarBehaviorInterface(BaseDataInterface):
    """Behavior interface"""

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem

        module_name = "Neural states"
        module_description = "Contains behavioral data concerning classified states."
        processing_module = get_module(nwbfile=nwbfile, name=module_name, description=module_description)

        # Sleep states
        sleep_states_file_path = session_path / f"{session_id}.SleepState.states.mat"
        if Path(sleep_states_file_path).exists():
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