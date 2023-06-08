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

        return metadata

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePathType] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        external_mode: bool = True,
        starting_frames: Optional[list] = None,
        chunk_data: bool = True,
        module_name: Optional[str] = None,
        module_description: Optional[str] = None,
        compression: Optional[str] = "gzip",
        compression_options: Optional[int] = None,
    ):
        """
        Convert the video data files to :py:class:`~pynwb.image.ImageSeries` and write them in the
        :py:class:`~pynwb.file.NWBFile`. Data is written in the :py:class:`~pynwb.image.ImageSeries` container as
        RGB. [times, x, y, 3-RGB].

        Parameters
        ----------
        nwbfile_path : FilePathType, optional
            Path for where to write or load (if overwrite=False) the NWB file.
            If specified, this context will always write to this location.
        nwbfile : NWBFile, optional
            nwb file to which the recording information is to be added
        metadata : dict, optional
            Dictionary of metadata information such as names and description of each video.
            Metadata should be passed for each video file passed in the file_paths.
            If storing as 'external mode', then provide duplicate metadata for video files that go in the
            same :py:class:`~pynwb.image.ImageSeries` container.
            Should be organized as follows::

                metadata = dict(
                    Behavior=dict(
                        Videos=[
                            dict(name="Video1", description="This is the first video.."),
                            dict(name="SecondVideo", description="Video #2 details..."),
                            ...
                        ]
                    )
                )
            and may contain most keywords normally accepted by an ImageSeries
            (https://pynwb.readthedocs.io/en/stable/pynwb.image.html#pynwb.image.ImageSeries).
            The list for the 'Videos' key should correspond one to the video files in the file_paths list.
            If multiple videos need to be in the same :py:class:`~pynwb.image.ImageSeries`, then supply the same value for "name" key.
            Storing multiple videos in the same :py:class:`~pynwb.image.ImageSeries` is only supported if 'external_mode'=True.
        overwrite : bool, default: False
            Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        stub_test : bool, default: False
            If ``True``, truncates the write operation for fast testing.
        external_mode : bool, default: True
            :py:class:`~pynwb.image.ImageSeries` may contain either video data or file paths to external video files.
            If True, this utilizes the more efficient method of writing the relative path to the video files (recommended).
        starting_frames : list, optional
            List of start frames for each video written using external mode.
            Required if more than one path is specified per ImageSeries in external mode.
        chunk_data : bool, default: True
            If True, uses a DataChunkIterator to read and write the video, reducing overhead RAM usage at the cost of
            reduced conversion speed (compared to loading video entirely into RAM as an array). This will also force to
            True, even if manually set to False, whenever the video file size exceeds available system RAM by a factor
            of 70 (from compression experiments). Based on experiments for a ~30 FPS system of ~400 x ~600 color
            frames, the equivalent uncompressed RAM usage is around 2GB per minute of video. The default is True.
        module_name: str, optional
            Name of the processing module to add the ImageSeries object to. Default behavior is to add as acquisition.
        module_description: str, optional
            If the processing module specified by module_name does not exist, it will be created with this description.
            The default description is the same as used by the conversion_tools.get_module function.
        compression: str, default: "gzip"
            Compression strategy to use for :py:class:`hdmf.backends.hdf5.h5_utils.H5DataIO`. For full list of currently
            supported filters, see
            https://docs.h5py.org/en/latest/high/dataset.html#lossless-compression-filters
        compression_options: int, optional
            Parameter(s) for compression filter. Currently, only supports the compression level (integer from 0 to 9) of
            compression="gzip".
        """

        file_paths = self.source_data["file_paths"]
        if starting_frames is None:
            starting_frames = self._starting_frames

        self._timestamps = self.get_original_timestamps(stub_test=stub_test)
        self.set_aligned_segment_starting_times(
            aligned_segment_starting_times=self.segment_starting_times, stub_test=stub_test
        )

        nwbfile_out = super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            stub_test=stub_test,
            external_mode=external_mode,
            starting_frames=starting_frames,
            chunk_data=chunk_data,
            module_name=module_name,
            module_description=module_description,
            compression=compression,
            compression_options=compression_options,
        )

        return nwbfile_out
