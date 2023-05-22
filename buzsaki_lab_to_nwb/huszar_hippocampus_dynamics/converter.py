from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from scipy.io import loadmat as loadmat_scipy

from neuroconv import NWBConverter

from behaviorinterface import (
    HuzsarBehaviorSleepInterface,
    HuszarBehavior8MazeInterface,
)

from sortinginterface import CellExplorerSortingInterface


class HuzsarNWBConverter(NWBConverter):
    """Primary conversion class for the Huzsar hippocampus data set."""

    data_interface_classes = dict(
        Sorting=CellExplorerSortingInterface,
        Behavior8Maze=HuszarBehavior8MazeInterface,
        BehaviorSleep=HuzsarBehaviorSleepInterface,
    )

    def __init__(self, source_data: dict, verbose: bool = True):
        super().__init__(source_data=source_data, verbose=verbose)

        self.session_folder_path = Path(self.data_interface_objects["Behavior8Maze"].source_data["folder_path"])
        self.session_id = self.session_folder_path.stem

    def get_metadata(self):
        metadata = super().get_metadata()
        session_file = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file.is_file(), f"Session file not found: {session_file}"

        session_mat = loadmat_scipy(session_file, simplify_cells=True)
        date = session_mat["session"]["general"]["date"]  # This does not contain the time
        # Conver date str to date object
        date = datetime.strptime(date, "%Y-%m-%d")
        # Build a datetime object and add the timezone from NY
        date = datetime.combine(date, datetime.min.time())
        tzinfo = ZoneInfo("America/New_York")  # This is the standard library
        date = date.replace(tzinfo=tzinfo)

        # Get today date
        metadata["NWBFile"]["session_start_time"] = date

        # Add additional NWBFile metadata
        # NOTE: experimenters is specifid in the metadata.yml file
        # experimenters = session_mat["session"]['general']['experimenters']
        # metadata["NWBFile"]["experimenter"] = experimenters if isinstance(experimenters, list) else [ experimenters ]
        metadata["NWBFile"]["notes"] = session_mat["session"]['general']['notes']

        # Add Subject metadata
        animal_metadata = session_mat["session"]['animal']
        metadata["Subject"]["subject_id"] = animal_metadata['name']
        
        def ensureProperSexValue(sex):
           if (sex == 'Female'): return 'F'
           if (sex == 'Male'): return 'M'
            
           return sex

        metadata["Subject"]["sex"] = ensureProperSexValue(animal_metadata['sex'])
        # metadata["Subject"]["species"] = animal_metadata['species'] # NOTE: Appropriate value added to metadata.yml file
        metadata["Subject"]["strain"] = animal_metadata['strain']
        metadata["Subject"]["genotype"] = animal_metadata['geneticLine']

        return metadata
