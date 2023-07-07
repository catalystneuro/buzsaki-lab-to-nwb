from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from neuroconv import NWBConverter
from scipy.io import loadmat as loadmat_scipy

from neuroconv.datainterfaces import NeuroScopeLFPInterface, NeuroScopeRecordingInterface

from ripplesinterface import (
    HuszarProcessingRipplesEventsInterface,
)


from behaviorinterface import (
    HuzsarBehaviorSleepInterface,
    HuszarBehavior8MazeInterface,
    HuszarBehavior8MazeRewardsInterface,
)

from epochsinterface import HuszarEpochsInterface
from trialsinterface import HuszarTrialsInterface

from neuroconv.datainterfaces import CellExplorerSortingInterface


class HuzsarNWBConverter(NWBConverter):
    """Primary conversion class for the Huzsar hippocampus data set."""

    data_interface_classes = dict(
        Recording=NeuroScopeRecordingInterface,
        LFP=NeuroScopeLFPInterface,
        Sorting=CellExplorerSortingInterface,
        Behavior8Maze=HuszarBehavior8MazeInterface,
        BehaviorSleep=HuzsarBehaviorSleepInterface,
        BehaviorRewards=HuszarBehavior8MazeRewardsInterface,
        Epochs=HuszarEpochsInterface,
        Trials=HuszarTrialsInterface,
        RippleEvents=HuszarProcessingRipplesEventsInterface,
    )

    def __init__(self, source_data: dict, verbose: bool = True):
        super().__init__(source_data=source_data, verbose=verbose)

        self.session_folder_path = Path(self.data_interface_objects["RippleEvents"].source_data["folder_path"])
        self.session_id = self.session_folder_path.stem

    def get_metadata(self):
        metadata = super().get_metadata()
        session_file = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file.is_file(), f"Session file not found: {session_file}"

        session_mat = loadmat_scipy(session_file, simplify_cells=True)
        date = self.session_id.split("_")[2]  # This does not contain the time

        # Convert date str to date object

        date = datetime.strptime("20" + date, "%Y%m%d")
        # Build a datetime object and add the timezone from NY
        date = datetime.combine(date, datetime.min.time())
        tzinfo = ZoneInfo("America/New_York")  # This is the standard library
        date = date.replace(tzinfo=tzinfo)

        # Get today date
        metadata["NWBFile"]["session_start_time"] = date

        # Add additional NWBFile metadata
        # NOTE: experimenters is specifid in the metadata.yml file
        metadata["NWBFile"]["session_id"] = session_mat["session"]["general"]["name"]

        possibleNote = session_mat["session"]["general"]["notes"]
        ignoredNotes = ["Notes:    Description from xml: "]
        if not any(x in possibleNote for x in ignoredNotes):
            metadata["NWBFile"]["notes"] = possibleNote

        # Add Subject metadata
        subject_metadata = session_mat["session"]["animal"]
        metadata["Subject"]["subject_id"] = subject_metadata["name"]

        if metadata["Subject"]["subject_id"] == "DATA":
            metadata["Subject"]["subject_id"] = "_".join(metadata["NWBFile"]["session_id"].split("_")[:2])
        metadata["Subject"]["sex"] = subject_metadata["sex"][0]
        metadata["Subject"]["strain"] = subject_metadata["strain"]
        metadata["Subject"]["genotype"] = subject_metadata["geneticLine"]

        # NOTE: No weight information because there isn't any surgery metadata

        return metadata
