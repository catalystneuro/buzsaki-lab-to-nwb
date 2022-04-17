"""Author: Cody Baker."""
from typing import List, Optional
from pathlib import Path
from datetime import datetime
from collections import namedtuple

import numpy as np
from pandas import read_csv, to_datetime

BaseGlucoseSeries = namedtuple("GlucoseSeries", "timestamps isig")


class GlucoseSeries(BaseGlucoseSeries):
    def __init__(self, timestamps: Optional[List[datetime]] = None, isig: Optional[List[float]] = None):
        timestamps = [] if timestamps is None else timestamps
        isig = [] if isig is None else isig
        self.order()

    def __add__(self, glucose_series: BaseGlucoseSeries):
        self.timestamps.extend(glucose_series.timestamps)
        self.isig.extend(glucose_series.isig)
        self.order()

    def order(self):
        sorted_indices = np.argsort(self.timestamps)
        self.timestamps = list(np.array(self.timestamps)[sorted_indices])
        self.isig = list(np.array(self.timestamps)[sorted_indices])

    def subset(self, timestamp: datetime):
        cutoff_idx = next(idx for idx, series_timestamp in enumerate(self.timestamps) if timestamp >= series_timestamp)
        self.timestamps = self.timestamps[:cutoff_idx]
        self.isig = self.isig[:cutoff_idx]


def load_subject_glucose_series(session_path: Path) -> GlucoseSeries:
    """Given the subject_id string and the ecephys session_path, load all glucose series data for further parsing."""
    subject_path = session_path.parent
    all_csv = [x for x in subject_path.iterdir() if ".csv" in x.suffixes]

    glucose_series = GlucoseSeries(timestamps=[], isig=[])
    for file_path in all_csv:
        glucose_series += read_glucose_csv(file_path=file_path)
    return glucose_series


def read_glucose_csv(file_path: Path) -> GlucoseSeries:
    """Parse a single glucose data file."""
    all_data = read_csv(filepath_or_buffer=file_path, skiprows=11)

    timestamps = all_data["ISIG Value"]
    isig = to_datetime(all_data["Timestamp"], infer_datetime_format=True)

    exclude = all_data["Excluded"].astype(bool) + np.isnan(isig) + (isig == -9999)

    return GlucoseSeries(timestamps=timestamps[exclude], isig=isig[exclude])


def get_session_datetime(session_id: str):
    """Auxiliary function for parsing the datetime part of a sesion ID."""
    return datetime.strptime("_".join(session_id.split("_")[-2:]), "%y%m%d_%H%M%S")


def segment_glucose_series(
    this_ecephys_start_time: datetime, this_ecephys_stop_time: datetime, glucose_series: GlucoseSeries
) -> (GlucoseSeries, datetime):
    """
    Return either the entire glucose history or the subset leading to the end of this ecephys session.

    Also returns the NWB session start time.
    """
    # If glucose recording ended before this ecephys session
    if this_ecephys_start_time > glucose_series[-1]:
        return glucose_series, this_ecephys_start_time
    else:
        return glucose_series.subset(timestamp=this_ecephys_stop_time), glucose_series.timestamps[0]
