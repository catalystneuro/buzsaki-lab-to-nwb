"""Author: Cody Baker."""
from typing import List, Dict
from pathlib import Path
from datetime import datetime

import numpy as np
from pandas import read_csv


def load_subject_glucose_series(session_path: Path):
    """Given the subject_id string and the ecephys session_path, load all glucose series data for further parsing."""
    subject_path = session_path.parent
    all_csv = [x for x in subject_path.iterdir if ".csv" in x.suffixes]

    all_glucose_data = dict()
    for file_path in all_csv:
        all_glucose_data.update(read_glucose_csv(file_path=file_path))

    all_timestamps = np.array(list(all_glucose_data.keys()))
    all_isig = np.array(list(all_glucose_data.values()))
    sort_indices = np.argsort(all_timestamps)
    ordered_glucose_data = {k: v for k, v in zip(all_timestamps[sort_indices], all_isig[sort_indices])}

    return ordered_glucose_data


def read_glucose_csv(file_path: Path) -> Dict[datetime, float]:
    """Parse a single glucose data file."""
    all_data = read_csv(filepath_or_buffer="C:/Users/Raven/Documents/TingleyD/CGM31.csv", skiprows=11)
    excluded = all_data["Excluded"].astype(bool)
    timestamps = [datetime.strptime(x, "%d/%m/%y %H:%M:%S") for x in all_data["Timestamp"][excluded]]
    isig_signal = all_data["ISIG Value"][excluded]

    valid_timestamp_to_isig = {
        timestamp: isig for timestamp, isig in zip(timestamps, isig_signal) if not np.isnan(isig) and isig != -9999
    }

    return valid_timestamp_to_isig


def get_subject_ecephys_session_start_times(session_path: Path) -> List[datetime]:
    """Return all the start times for the ecephys sessions for this subject."""
    subject_path = session_path.parent
    all_session_names = [x.name for x in subject_path.iterdir if x.isdir()]
    all_datetime_strings = [session_name.strip("_")[:-2] for session_name in all_session_names]

    all_timestamps = np.sort(all_datetime_strings)
    return all_timestamps
