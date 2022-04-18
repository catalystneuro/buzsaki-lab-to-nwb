"""Authors: Cody Baker."""
from datetime import datetime

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils import FilePathType
from pynwb import TimeSeries, H5DataIO

from .tingley_metabolic_utils import load_subject_glucose_series, segment_glucose_series


class TingleyMetabolicGlucoseInterface(BaseDataInterface):
    """Glucose data interface for the Tingley metabolic project."""

    def __init__(self, session_path: FilePathType, ecephys_start_time: str, ecephys_stop_time: str):
        subject_glucose_series = load_subject_glucose_series(session_path=session_path)
        session_glucose_series, session_start_time = segment_glucose_series(
            ecephys_start_time=datetime.fromisoformat(ecephys_start_time),
            ecephys_stop_time=datetime.fromisoformat(ecephys_stop_time),
            glucose_series=subject_glucose_series,
        )
        self.session_start_time = session_start_time
        self.glucose_series = session_glucose_series

    def run_conversion(self, nwbfile, metadata):
        print(self.glucose_series.isig)
        nwbfile.add_acquisition(
            TimeSeries(
                name="GlucoseLevel",
                description="Raw current from Medtronic iPro2 ISIG tracking.",
                unit="nA",
                data=H5DataIO(self.glucose_series.isig),  # should not need iterative write
                conversion=1.0,
                timestamps=H5DataIO(self.glucose_series.timestamps),
            ),
        )
