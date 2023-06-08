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


def generate_neurolight_device_metadata() -> dict:
    # Create device
    name = "N1-F21-O36 | 18"
    manufacturer = "Neurolight Technologies"
    description = (
        "12 µLEDs, 10 x 15 µm each, 3 per shank\n"
        "Emission Peak λ = 460 nm and FWHM = 40 nm\n"
        "Typical irradiance of 33 mW/mm² (@ max operating current of 100 µA)\n"
        "32 recording channels, 8 per shank\n"
        "Electrode impedance of 1000 - 1500 kΩ at 1 kHz\n"
    )

    device_metadata = dict(name=name, description=description, manufacturer=manufacturer)

    return device_metadata


def correct_device_metadata(metadata):
    neurolight_device_metadata = generate_neurolight_device_metadata()
    metadata["Ecephys"]["Device"] = [neurolight_device_metadata]  # Needs to be a list because neuroconv convention
    electrode_group_metadata_list = metadata["Ecephys"]["ElectrodeGroup"]
    for electrode_group_metadata in electrode_group_metadata_list:
        electrode_group_metadata["location"] = "CA1"
        electrode_group_metadata["device"] = neurolight_device_metadata["name"]

    return metadata


class ValeroLFPInterface(NeuroScopeLFPInterface):
    def __init__(
        self,
        file_path: FilePathType,
        folder_path: FolderPathType,
        gain: Optional[float] = None,
        xml_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
    ):
        super().__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)
        self.recording_extractor._sampling_frequency = 1250.0

        # Update the sampling frequency of the segments
        for segment in self.recording_extractor._recording_segments:
            segment.sampling_frequency = 1250.0

        # Add further properties
        add_extra_properties_to_recorder(self.recording_extractor, folder_path)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata = correct_device_metadata(metadata)

        return metadata


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
        super().__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path, verbose=verbose, es_key=es_key)

        # Add further properties
        add_extra_properties_to_recorder(self.recording_extractor, folder_path)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata = correct_device_metadata(metadata)

        return metadata
