from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from scipy.io import loadmat as loadmat_scipy

from neuroconv import NWBConverter

from neuroconv.datainterfaces import NeuroScopeLFPInterface, NeuroScopeRecordingInterface

# from laserpulsesinterface import ValeroLaserPulsesInterface
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


from sortinginterface import CellExplorerSortingInterface


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

        self.session_folder_path = Path(self.data_interface_objects["Behavior8Maze"].source_data["folder_path"])
        self.session_id = self.session_folder_path.stem

        # Add electrode locations (modeled after yutavcnwbconverter)
        electrode_chan_map_file_path = self.session_folder_path / "chanMap.mat"
        chan_map = loadmat_scipy(electrode_chan_map_file_path)
        xcoords = [x[0] for x in chan_map["xcoords"]]
        ycoords = [y[0] for y in chan_map["ycoords"]]
        kcoords = [y[0] for y in chan_map["kcoords"]]

        for channel_id in chan_map["chanMap0ind"]:
            if self.data_interface_objects.get("LFP"):
                self.data_interface_objects["LFP"].recording_extractor.set_channel_locations(
                    locations=[xcoords[channel_id], ycoords[channel_id], kcoords[channel_id]], channel_ids=channel_id
                )

            if self.data_interface_objects.get("Recording"):
                self.data_interface_objects["Recording"].recording_extractor.set_channel_locations(
                    locations=[xcoords[channel_id], ycoords[channel_id], kcoords[channel_id]], channel_ids=channel_id
                )

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
        metadata["NWBFile"]["session_id"] = session_mat["session"]["general"]["name"]

        possibleNote = session_mat["session"]["general"]["notes"]
        ignoredNotes = ["Notes:    Description from xml: "]
        if not any(x in possibleNote for x in ignoredNotes):
            metadata["NWBFile"]["notes"] = possibleNote

        # Add Subject metadata
        subject_metadata = session_mat["session"]["animal"]
        metadata["Subject"]["subject_id"] = subject_metadata["name"]
        metadata["Subject"]["sex"] = subject_metadata["sex"][0]
        metadata["Subject"]["strain"] = subject_metadata["strain"]
        metadata["Subject"]["genotype"] = subject_metadata["geneticLine"]

        # NOTE: No weight information because there isn't any surgery metadata

        return metadata
