from pathlib import Path
from typing import Union

import numpy as np
from neuroconv import BaseDataInterface
from neuroconv.datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from neuroconv.tools.spikeinterface.spikeinterface import add_electrodes
from pymatreader import read_mat
from pynwb import NWBFile
from spikeinterface.core.numpyextractors import NumpyRecording


class HuszarElectrodeInterface(BaseDataInterface):
    def __init__(self, folder_path: Union[str, Path], verbose: bool = True):
        folder_path = Path(folder_path)
        self.chan_map_file_path = folder_path / "chanMap.mat"
        assert self.chan_map_file_path.exists(), f"chanMap.mat file not found in {folder_path}"

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        mat_file = read_mat(self.chan_map_file_path)
        channel_groups = mat_file["connected"]
        channel_group_names = [f"Group{group_index + 1}" for group_index in channel_groups]

        channel_indices = mat_file["chanMap0ind"]

        # Follow Neuroscope convention
        channel_ids = [str(channel_indices[i]) for i in channel_indices]
        channel_name = [
            f"ch{channel_index}grp{channel_group}"
            for channel_index, channel_group in zip(channel_indices, channel_groups)
        ]

        x_coords = mat_file["xcoords"]
        y_coords = mat_file["ycoords"]
        locations = np.array((x_coords, y_coords)).T.astype("float32")

        num_channels = len(channel_indices)
        traces_list = [np.ones(shape=(1, num_channels))]
        sampling_frequency = 30_000.0
        recording = NumpyRecording(
            traces_list=traces_list, sampling_frequency=sampling_frequency, channel_ids=channel_ids
        )
        recording.set_channel_locations(channel_ids=channel_ids, locations=locations)

        recording.set_property(key="channel_name", values=channel_name)

        # This should transform to microvolts which is the standard in spikeinterface
        recording.set_channel_gains(channel_ids=channel_ids, gains=np.ones(num_channels) * 0.195)
        # Probably we should not use this if we use Neuroscope convention
        # recording.set_channel_offsets(channel_ids=channel_ids, offsets=np.ones(num_channels) * -32768 * 0.195)
        recording.set_property(key="group", ids=channel_ids, values=channel_groups)
        recording.set_property(key="group_name", ids=channel_ids, values=channel_group_names)

        add_electrodes(recording=recording, nwbfile=nwbfile)
