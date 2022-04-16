"""Author: Cody Baker."""
from typing import List, Dict
from pathlib import Path
from datetime import datetime

import numpy as np
from pandas import read_csv, to_datetime


def load_subject_glucose_series(session_path: Path) -> Dict[datetime, float]:
    """Given the subject_id string and the ecephys session_path, load all glucose series data for further parsing."""
    subject_path = session_path.parent
    all_csv = [x for x in subject_path.iterdir() if ".csv" in x.suffixes]

    all_glucose_data = dict()
    for file_path in all_csv:
        all_glucose_data.update(read_glucose_csv(file_path=file_path))

    all_timestamps = np.array(list(all_glucose_data.keys()))
    all_isig = np.array(list(all_glucose_data.values()))
    sorted_indices = np.argsort(all_timestamps)
    glucose_series = {k: v for k, v in zip(all_timestamps[sorted_indices], all_isig[sorted_indices])}

    return glucose_series


def read_glucose_csv(file_path: Path) -> Dict[datetime, float]:
    """Parse a single glucose data file."""
    all_data = read_csv(filepath_or_buffer=file_path, skiprows=11)
    excluded = all_data["Excluded"].astype(bool)

    valid_timestamp_to_isig = {
        datetime_timestamp: isig_value
        for datetime_timestamp, isig_value in zip(
            to_datetime(all_data["Timestamp"][excluded], infer_datetime_format=True), all_data["ISIG Value"][excluded]
        )
        if not np.isnan(isig_value) and isig_value != -9999
    }

    return valid_timestamp_to_isig


def get_subject_ecephys_session_start_times(session_path: Path) -> List[datetime]:
    """Return all the start times for the ecephys sessions for this subject."""
    subject_path = session_path.parent
    subject_session_ids = [x.name for x in subject_path.iterdir() if x.is_dir()]
    return sorted([get_session_datetime(session_id) for session_id in subject_session_ids])


def get_session_datetime(session_id: str):
    """Auxiliary function for parsing the datetime part of a sesion ID."""
    return datetime.strptime("_".join(session_id.split("_")[-2:]), "%y%m%d_%H%M%S")


def segment_glucose_series(
    this_ecephys_start_time: datetime,
    glucose_series: Dict[datetime, float],
    ecephys_start_times: List[datetime],
    ecephys_end_times: List[datetime],
) -> (Dict[datetime, float], datetime):
    """1."""
    glucose_timestamps = list(glucose_series.keys())

    # If glucose recording ended before this ecephys session
    if this_ecephys_start_time > glucose_timestamps[-1]:
        return None, this_ecephys_start_time

    segments = dict()
    ecephys_start_times_to_segment_number = dict()
    # Calculate segments
    if ecephys_start_times[0] > glucose_timestamps[0]:  # if first ecephys session started before glucose recording
        segments.update({0: (ecephys_start_times[0], ecephys_end_times[0])})
    else:
        if ecephys_start_times[0] > glucose_timestamps[-1]:  # if glucose recording ended before
            segments.update({0: (glucose_timestamps[0], ecephys_end_times[0])})

    glucose_series_per_segment = dict()
    for segment_number, (start, stop) in segments.items():
        glucose_series_per_segment.update({segment_number: {k: v for k, v in glucose_series if start <= k <= stop}})

    # Get the segment for this session
    this_session_segment_number = ecephys_start_times_to_segment_number[this_ecephys_start_time]
    return glucose_series_per_segment[this_session_segment_number], segments[this_session_segment_number][0]
