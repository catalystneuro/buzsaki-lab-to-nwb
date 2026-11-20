"""Author: Cody Baker."""

import re
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


def get_session_datetime_key(session_id: str) -> str:
    """The date and time fields of a session ID (its last two fields), joined by an underscore.

    The fields can be separated by underscores (CGM1_210125_143404, the session folders) or by dashes
    (CGM1-210125-143404, how some files on DANDI are named). Both give 210125_143404.
    """
    return "_".join(re.split("[-_]", session_id)[-2:])


def get_dandi_session_datetime_key(dandi_path: str) -> str:
    """The date and time fields of the session of a DANDI asset path.

    Both sub-CGM1/sub-CGM1_ses-CGM1_210125_143404_ecephys.nwb and sub-CGM1/sub-CGM1_ses-CGM1-210125-143404_ecephys.nwb
    give 210125_143404.
    """
    file_name = dandi_path.split("/")[-1]
    without_modality = file_name.rsplit("_", maxsplit=1)[0]  # drop the trailing "_ecephys.nwb"
    return get_session_datetime_key(without_modality)
