"""Author: Cody Baker."""
from typing import List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

import numpy as np
from pandas import read_csv, to_datetime


@dataclass
class GlucoseSeries:
    # timestamps: Optional[List[datetime]] = None
    # isig: Optional[List[float]] = None

    def __init__(self, timestamps: Optional[List[datetime]] = None, isig: Optional[List[float]] = None):
        super().__init__()
        self.timestamps = [] if timestamps is None else timestamps
        self.isig = [] if isig is None else isig
        self.order()

    def __add__(self, glucose_series):
        self.timestamps.extend(glucose_series.timestamps)
        self.isig.extend(glucose_series.isig)
        self.order()
        return self

    def order(self):
        sorted_indices = np.argsort(self.timestamps)
        # self.timestamps = list(np.array(self.timestamps)[sorted_indices])
        unsorted_timestamps = list(self.timestamps)
        self.timestamps = [unsorted_timestamps[idx] for idx in sorted_indices]
        self.isig = list(np.array(self.isig)[sorted_indices])

    def subset(self, timestamp: datetime):
        cutoff_idx = next(idx for idx, series_timestamp in enumerate(self.timestamps) if timestamp >= series_timestamp)
        print(cutoff_idx)
        timestamps = self.timestamps[:cutoff_idx]
        isig = self.isig[:cutoff_idx]
        return GlucoseSeries(timestamps=timestamps, isig=isig)


def load_subject_glucose_series(session_path) -> GlucoseSeries:
    """Given the subject_id string and the ecephys session_path, load all glucose series data for further parsing."""
    subject_path = Path(session_path).parent
    all_csv = [x for x in subject_path.iterdir() if ".csv" in x.suffixes]

    glucose_series = GlucoseSeries()
    for file_path in all_csv:
        glucose_series += read_glucose_csv(file_path=file_path)
    return glucose_series


def read_glucose_csv(file_path: Path) -> GlucoseSeries:
    """Parse a single glucose data file."""
    all_data = read_csv(filepath_or_buffer=file_path, skiprows=11)

    isig = all_data["ISIG Value"]
    exclude = all_data["Excluded"].astype(bool) + (1 - np.isnan(isig)) + (isig == -9999)
    valid_isig = isig[exclude]
    valid_timestamps = [
        x.to_pydatetime() for x in to_datetime(all_data["Timestamp"][exclude], infer_datetime_format=True)
    ]

    return GlucoseSeries(timestamps=valid_timestamps, isig=valid_isig)


def get_session_datetime(session_id: str):
    """Auxiliary function for parsing the datetime part of a sesion ID."""
    return datetime.strptime("_".join(session_id.split("_")[-2:]), "%y%m%d_%H%M%S")


def segment_glucose_series(
    ecephys_start_time: datetime, ecephys_stop_time: datetime, glucose_series: GlucoseSeries
) -> (GlucoseSeries, datetime):
    """
    Return either the entire glucose history or the subset leading to the end of this ecephys session.

    Also returns the NWB session start time.
    """
    # If glucose recording ended before this ecephys session
    if ecephys_start_time > glucose_series.timestamps[-1]:
        return glucose_series, ecephys_start_time
    else:
        return glucose_series.subset(timestamp=ecephys_stop_time), glucose_series.timestamps[0]
