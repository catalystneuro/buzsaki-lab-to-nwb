from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.datainterfaces import VideoInterface
from neuroconv.utils import FilePathType, FolderPathType
from pymatreader import read_mat
from pynwb import NWBFile


class ValeroVideoInterface(VideoInterface):
    def __init__(self, folder_path: FolderPathType, verbose: bool = False):
        self.session_folder_path = Path(folder_path)
        self.session_id = self.session_folder_path.stem
        session_file_path = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file_path.is_file(), session_file_path

        mat_file = read_mat(session_file_path)
        epoch_list = mat_file["session"]["epochs"]

        name_of_folders = [self.session_folder_path / f"{epoch['name']}" for epoch in epoch_list]
        start_time_folder_tuples = ((epoch["startTime"], folder) for epoch, folder in zip(epoch_list, name_of_folders))
        start_time_folder_tuples = [(_, folder) for _, folder in start_time_folder_tuples if folder.is_dir()]

        # For each of the folder in name_of_folders look for the .avi file and
        # This can't be done with a rglob because some sessions like `fCamk3_201030_sess12` contain sub-nested sessions.
        epoch_to_video_info = {}
        for start_time, folder in start_time_folder_tuples:
            video_file_paths = list(folder.glob("*.avi"))
            assert len(video_file_paths) <= 1, "There should be only one .avi file in each epoch folder"
            if len(video_file_paths) == 1:  # If a video is found add it to the dict
                epoch_to_video_info[folder.name] = dict(file_path=video_file_paths[0], start_time=start_time)

        # Now we have to sort the epochs, and therefore the videos, by start time
        sorted_items = sorted(epoch_to_video_info.items(), key=lambda item: item[1]["start_time"])
        self.sorted_epoch_to_video_info = {k: v for k, v in sorted_items}
        file_paths = [info["file_path"] for info in self.sorted_epoch_to_video_info.values()]

        super().__init__(file_paths, verbose)

        self._segment_starting_times = [info["start_time"] for info in self.sorted_epoch_to_video_info.values()]
