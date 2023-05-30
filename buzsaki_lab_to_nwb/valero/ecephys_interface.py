from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.datainterfaces import (
    NeuroScopeLFPInterface,
    NeuroScopeRecordingInterface,
)
from neuroconv.utils import FilePathType, FolderPathType
from pymatreader import read_mat


def add_extra_properties_to_recorder(recording_extractor, folder_path):
    session_path = Path(folder_path)
    session_id = session_path.stem

    # We use the behavioral cellinfo file to get the trial intervals
    chan_map_path = session_path / f"chanMap.mat"
    assert chan_map_path.exists(), f"chanMap.mat file not found: {chan_map_path}"

    mat_file = read_mat(chan_map_path)
    channel_ids_in_matlab = mat_file["chanMap0ind"]

    channel_ids_in_matlab = [str(channel_ids_in_matlab[i]) for i in channel_ids_in_matlab]

    x_coords = mat_file["xcoords"]
    y_coords = mat_file["ycoords"]

    locations = np.array((x_coords, y_coords)).T.astype("float32")
    recording_extractor.set_channel_locations(channel_ids=channel_ids_in_matlab, locations=locations)

    recording_extractor.set_property(key="brain_area", values=["CA1"] * recording_extractor.get_num_channels())


class ValeroLFPInterface(NeuroScopeLFPInterface):
    def __init__(
        self,
        file_path: FilePathType,
        folder_path: FolderPathType,
        gain: Optional[float] = None,
        xml_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
    ):
        super().__init__(file_path, gain, xml_file_path)
        self.recording_extractor._sampling_frequency = 1250.0

        # Update the sampling frequency of the segments
        for segment in self.recording_extractor._recording_segments:
            segment.sampling_frequency = 1250.0

        # Add further properties
        add_extra_properties_to_recorder(self.recording_extractor, folder_path)


class ValeroRawInterface(NeuroScopeRecordingInterface):
    ExtractorName = "NeuroScopeRecordingExtractor"

    def __init__(
        self,
        file_path: FilePathType,
        folder_path: FolderPathType,
        gain: Optional[float] = None,
        xml_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        super().__init__(file_path, gain, xml_file_path, verbose, es_key)

        # Add further properties
        add_extra_properties_to_recorder(self.recording_extractor, folder_path)
