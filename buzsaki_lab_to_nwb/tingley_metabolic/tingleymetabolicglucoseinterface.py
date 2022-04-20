"""Authors: Cody Baker."""
from datetime import datetime

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils import FilePathType
from pynwb import TimeSeries, H5DataIO

from .tingley_metabolic_utils import load_subject_glucose_series  # , segment_glucose_series


class TingleyMetabolicGlucoseInterface(BaseDataInterface):
    """Glucose data interface for the Tingley metabolic project."""

    def __init__(self, session_path: FilePathType, ecephys_start_time: str, ecephys_stop_time: str):
        glucose_timestamps, glucose_isig = load_subject_glucose_series(session_path=session_path)
        self.session_start_time = glucose_timestamps[0]
        glucose_timestamps_floats_from_datetime = [
            (glucose_timestamp - self.session_start_time).total_seconds() for glucose_timestamp in glucose_timestamps
        ]
        self.glucose_timestamps = glucose_timestamps_floats_from_datetime
        self.glucose_isig = glucose_isig

    def run_conversion(self, nwbfile, metadata):
        nwbfile.add_acquisition(
            TimeSeries(
                name="GlucoseLevel",
                description="Raw current from Medtronic iPro2 ISIG tracking.",
                unit="nA",
                data=H5DataIO(self.glucose_isig),  # should not need iterative write
                conversion=1.0,
                timestamps=H5DataIO(self.glucose_timestamps),
            ),
        )
