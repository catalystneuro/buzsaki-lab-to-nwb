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
        start_times = [epoch["startTime"] for epoch in epoch_list]
        assert all([folder.is_dir() for folder in name_of_folders]), "Some epochs have missing folder for this session"

        # For each of the folder in name_of_folders look for the .avi file and
        # This can't be done with a rglob because some sessions like `fCamk3_201030_sess12` contain sub-nested sessions.
        epoch_to_video_info = {}
        for folder, start_time in zip(name_of_folders, start_times):
            video_file_paths = list(folder.glob("*.avi"))
            assert len(video_file_paths) <= 1, "There should be only one .avi file in each epoch folder"
            if len(video_file_paths) == 1:
                epoch_to_video_info[folder.name] = dict(file_path=video_file_paths[0], start_time=start_time)

        # Now we have to sort the epochs by start time
        sorted_items = sorted(epoch_to_video_info.items(), key=lambda item: item[1]["start_time"])
        self.sorted_epoch_to_video_info = {k: v for k, v in sorted_items}
        file_paths = [info["file_path"] for info in self.sorted_epoch_to_video_info.values()]

        super().__init__(file_paths, verbose)

        self._segment_starting_times = [info["start_time"] for info in self.sorted_epoch_to_video_info.values()]

    # def run_conversion(
    #     self,
    #     nwbfile_path: Optional[FilePathType] = None,
    #     nwbfile: Optional[NWBFile] = None,
    #     metadata: Optional[dict] = None,
    #     overwrite: bool = False,
    #     stub_test: bool = False,
    #     external_mode: bool = True,
    #     starting_frames: Optional[list] = None,
    #     chunk_data: bool = True,
    #     module_name: Optional[str] = None,
    #     module_description: Optional[str] = None,
    #     compression: Optional[str] = "gzip",
    #     compression_options: Optional[int] = None,
    # ):

    #     super().run_conversion(
    #     nwbfile_path=nwbfile_path,
    #     nwbfile=nwbfile,
    #     metadata=metadata,
    #     overwrite=overwrite,
    #     stub_test=stub_test,
    #     external_mode=external_mode,
    #     starting_frames=starting_frames,
    #     chunk_data=chunk_data,
    #     module_name=module_name,
    #     module_description=module_description,
    #     compression=compression,
    #     compression_options=compression_options,
    # )
