from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.datainterfaces import VideoInterface
from neuroconv.utils import FilePathType, FolderPathType
from neuroconv.utils.json_schema import get_base_schema, get_schema_from_hdmf_class
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.image import ImageSeries


class ValeroVideoInterface(VideoInterface):
    def __init__(self, folder_path: FolderPathType, verbose: bool = False):
        self.session_folder_path = Path(folder_path)
        self.session_id = self.session_folder_path.stem
        session_file_path = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file_path.is_file(), session_file_path

        ignore_fields = ["animal", "behavioralTracking", "timeSeries", "spikeSorting", "extracellular", "brainRegions"]
        mat_file = read_mat(session_file_path, ignore_fields=ignore_fields)

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

        from neuroconv.datainterfaces.behavior.video.video_utils import (
            VideoCaptureContext,
        )

        self._starting_frames = [0]
        for file_index, file_path in enumerate(file_paths):
            with VideoCaptureContext(file_path=str(file_path)) as video_capture:
                self._starting_frames.append(video_capture.get_video_frame_count())

        self._starting_frames = self._starting_frames[:-1]
        super().__init__(file_paths, verbose)

        self.segment_starting_times = [info["start_time"] for info in self.sorted_epoch_to_video_info.values()]

    def get_metadata(self):
        metadata = super().get_metadata()

        file_paths = self.source_data["file_paths"]
        if file_paths:
            behavior_metadata = dict(
                Videos=[
                    dict(
                        name=f"ImageSeriesTrackingVideo{index + 1}",
                        description="Video recorded with Basler camera.",
                        unit="Frames",
                    )
                    for index, file_path in enumerate(self.source_data["file_paths"])
                ]
            )
            metadata["Behavior"] = behavior_metadata
        else:
            metadata["Behavior"].pop("Videos")  # Avoid the schema complaining

        return metadata

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        image_series_metadata_schema = get_schema_from_hdmf_class(ImageSeries)
        # TODO: in future PR, add 'exclude' option to get_schema_from_hdmf_class to bypass this popping
        exclude = ["format", "conversion", "starting_time", "rate"]
        for key in exclude:
            image_series_metadata_schema["properties"].pop(key)
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        if len(self.source_data["file_paths"]) > 0:
            metadata_schema["properties"]["Behavior"].update(
                required=["Videos"],
                properties=dict(
                    Videos=dict(
                        type="array",
                        minItems=1,
                        items=image_series_metadata_schema,
                    )
                ),
            )
        return metadata_schema

    def add_to_nwbfile(
        self,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        external_mode: bool = True,
        starting_frames: Optional[list] = None,
        chunk_data: bool = True,
        module_name: Optional[str] = None,
        module_description: Optional[str] = None,
        compression: Optional[str] = "gzip",
        compression_options: Optional[int] = None,
    ):
        file_paths = self.source_data["file_paths"]
        if file_paths:
            if starting_frames is None:
                starting_frames = self._starting_frames

            self._timestamps = self.get_original_timestamps(stub_test=stub_test)
            self.set_aligned_segment_starting_times(
                aligned_segment_starting_times=self.segment_starting_times, stub_test=stub_test
            )

            nwbfile = super().add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                stub_test=stub_test,
                external_mode=external_mode,
                starting_frames=starting_frames,
                chunk_data=chunk_data,
                module_name=module_name,
                module_description=module_description,
                compression=compression,
                compression_options=compression_options,
            )

            return nwbfile
        else:
            from warnings import warn

            warn(f"No video files found for session {self.session_id} . Skipping video interface.")
            nwbfile
