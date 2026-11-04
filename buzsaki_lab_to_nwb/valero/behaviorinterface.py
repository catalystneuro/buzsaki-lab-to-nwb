"""Position and rewards on the linear track of a Valero session (DANDI:000568)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.behavior import Position, SpatialSeries
from pynwb.event import EventsTable
from pynwb.file import NWBFile

# The lab's tracking is in cm (the linearized position runs from 0 to 110 cm, the length of the track)
METERS_PER_CM = 0.01
TRACK = "a PVC linear track 110 cm long and 6.35 cm wide"


def read_position(session_path: Path):
    """(timestamps, position dict, source file name) from Behavior.mat, or from Tracking.Behavior.mat if absent."""
    session_id = session_path.name
    for suffix, key in ((".Behavior.mat", "behavior"), (".Tracking.Behavior.mat", "tracking")):
        file_path = session_path / f"{session_id}{suffix}"
        if file_path.is_file():
            data = read_mat(str(file_path), variable_names=[key])[key]
            return data, file_path.name
    return None, None


class ValeroBehaviorLinearTrackInterface(BaseDataInterface):
    """Position on the linear track: camera (x, y) and linearized position."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        data, file_name = read_position(self.session_path)
        if data is None:
            return
        timestamps = np.asarray(data["timestamps"], dtype=float)
        position = data["position"]
        container = Position(name="LinearMazePositionTracking")
        container.add_spatial_series(
            SpatialSeries(
                name="SpatialSeriesRaw",
                description=f"(x, y) position of the mouse on {TRACK}, tracked from above with a Basler camera, in "
                f"cm (from {file_name})",
                data=np.column_stack((position["x"], position["y"])),
                reference_frame="camera coordinates, in cm",
                unit="meters",
                conversion=METERS_PER_CM,
                timestamps=timestamps,
            )
        )
        if "lin" in position:
            container.add_spatial_series(
                SpatialSeries(
                    name="SpatialSeriesLinearized",
                    description=f"linearized position of the mouse on the track, 0 to 110 cm (from {file_name})",
                    data=np.asarray(position["lin"], dtype=float),
                    reference_frame="0 is one end of the track",
                    unit="meters",
                    conversion=METERS_PER_CM,
                    timestamps=nwbfile_timestamps_link(container),
                )
            )
        get_module(nwbfile, "behavior", "behavior and brain states").add(container)


def nwbfile_timestamps_link(container: Position):
    """Share the timestamps of the raw position series."""
    return container.spatial_series["SpatialSeriesRaw"]


class ValeroBehaviorLinearTrackRewardsInterface(BaseDataInterface):
    """Water rewards at the two ends of the linear track (Behavior.mat events)."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        file_path = self.session_path / f"{self.session_path.name}.Behavior.mat"
        if not file_path.is_file():
            return
        events = read_mat(str(file_path), variable_names=["behavior"])["behavior"]["events"]
        rows = [(float(time), "left") for time in np.atleast_1d(events["lReward"])]
        rows += [(float(time), "right") for time in np.atleast_1d(events["rReward"])]
        rows = sorted(row for row in rows if np.isfinite(row[0]))
        if not rows:
            return
        table = EventsTable(
            name="rewards",
            description="water rewards at the ends of the linear track (Behavior.mat events.lReward and rReward)",
        )
        table.add_column(name="side", description="end of the track with the reward: left (lReward) or right (rReward)")
        for time, side in rows:
            table.add_row(timestamp=time, side=side)
        nwbfile.add_events_table(table)
