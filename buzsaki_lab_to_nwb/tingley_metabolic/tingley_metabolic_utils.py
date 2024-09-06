"""Author: Cody Baker."""
from typing import List
from pathlib import Path
from datetime import datetime

import numpy as np
from pandas import read_csv, to_datetime


def load_subject_glucose_series(session_path) -> (List[datetime], List[float]):
    """Given the subject_id string and the ecephys session_path, load all glucose series data for further parsing."""
    all_csv = [x for x in Path(session_path).iterdir() if ".csv" in x.suffixes]
    if not all_csv:
        subject_path = Path(session_path).parent
        all_csv = [x for x in subject_path.iterdir() if ".csv" in x.suffixes]

    timestamps = []
    isig = []
    for file_path in all_csv:
        sub_timestamps, sub_isig = read_glucose_csv(file_path=file_path)
        timestamps.extend(sub_timestamps)
        isig.extend(sub_isig)
    return timestamps, isig


def read_glucose_csv(file_path: Path) -> (List[datetime], List[float]):
    """Parse a single glucose data file."""
    all_data = read_csv(filepath_or_buffer=file_path, skiprows=11)

    isig = all_data["ISIG Value"]
    exclude_col = all_data["Excluded"]
    exclude_col.fillna(False, inplace=True)
    exclude = (exclude_col.astype(bool) + np.isnan(isig) + (isig == -9999)).astype(bool)
    valid_isig = isig[exclude == 0]
    valid_timestamps = [
        x.to_pydatetime() for x in to_datetime(all_data["Timestamp"][exclude == 0], infer_datetime_format=True)
    ]

    return valid_timestamps, list(valid_isig)


def get_session_datetime(session_id: str):
    """Auxiliary function for parsing the datetime part of a sesion ID."""
    return datetime.strptime("_".join(session_id.split("_")[-2:]), "%y%m%d_%H%M%S")
