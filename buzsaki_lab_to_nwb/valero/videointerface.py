"""Behavior videos of a Valero session (DANDI:000568), referenced as external files."""

import os
import struct
from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pynwb import NWBFile
from pynwb.image import ImageSeries

from .behaviorinterface import read_position
from .valeroutils import as_list, read_session


def read_avi_header(file_path: Path) -> tuple:
    """(number of frames, frames per second) from the AVI main header (and the OpenDML header, if any)."""
    with open(file_path, "rb") as file:
        head = file.read(1 << 16)
    index = head.find(b"avih")
    if index < 0:
        raise ValueError(f"{file_path} has no AVI main header")
    microseconds_per_frame, _, _, _, total_frames = struct.unpack("<5I", head[index + 8 : index + 28])
    dml = head.find(b"dmlh")
    if dml >= 0:
        total_frames = struct.unpack("<I", head[dml + 8 : dml + 12])[0]
    return total_frames, 1e6 / microseconds_per_frame


class ValeroVideoInterface(BaseDataInterface):
    """One ImageSeries referencing the .avi file of each epoch folder that has one.

    The frame times are not in the source: each video starts at the first tracking sample in its epoch and runs at
    the frame rate of its header.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        epochs = as_list(read_session(self.session_path)["epochs"])
        self.videos = []
        for epoch in sorted(epochs, key=lambda epoch: float(epoch["startTime"])):
            folder = self.session_path / str(epoch["name"])
            files = sorted(folder.glob("*.avi")) if folder.is_dir() else []
            if len(files) == 1:
                self.videos.append((files[0], float(epoch["startTime"]), float(epoch["stopTime"])))

    def add_to_nwbfile(
        self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, nwbfile_path: Optional[str] = None
    ):
        if not self.videos:
            return
        tracking, _ = read_position(self.session_path)
        tracking_times = np.asarray(tracking["timestamps"], dtype=float) if tracking is not None else np.array([])
        external_files, starting_frames, timestamps, notes = [], [], [], []
        for file_path, epoch_start, epoch_stop in self.videos:
            n_frames, rate = read_avi_header(file_path)
            in_epoch = tracking_times[(tracking_times >= epoch_start) & (tracking_times < epoch_stop)]
            start = float(in_epoch[0]) if in_epoch.size else epoch_start
            if in_epoch.size and in_epoch.size != n_frames:
                notes.append(f"{file_path.name} has {n_frames} frames and the tracking {in_epoch.size} samples")
            starting_frames.append(sum(len(times) for times in timestamps))
            timestamps.append(start + np.arange(n_frames) / rate)
            base = Path(nwbfile_path).parent if nwbfile_path else self.session_path
            external_files.append(os.path.relpath(file_path, base))
        nwbfile.add_acquisition(
            ImageSeries(
                name="ImageSeriesTrackingVideo",
                description=(
                    "videos of the linear track recorded with a Basler camera, one per track epoch, stored as "
                    "external files. The source has no frame times: each video starts at the first tracking sample "
                    "of its epoch and runs at the frame rate of its header" + "".join(f"; {note}" for note in notes)
                ),
                external_file=external_files,
                starting_frame=starting_frames,
                format="external",
                **(
                    dict(starting_time=float(timestamps[0][0]), rate=float(rate), num_samples=len(timestamps[0]))
                    if len(timestamps) == 1
                    else dict(timestamps=np.concatenate(timestamps))
                ),
                unit="n.a.",
            )
        )
