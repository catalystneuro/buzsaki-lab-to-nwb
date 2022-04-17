"""Authors: Cody Baker."""
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import TimeSeries, H5DataIO

from .tingley_metabolic_utils import GlucoseSeries


class TingleyMetabolicGlucoseInterface(BaseDataInterface):
    """Glucose data interface for the Tingley metabolic project."""

    def __init__(self, glucose_series: GlucoseSeries):
        self.glucose_series = glucose_series

    def run_conversion(self, nwbfile):
        nwbfile.add_acquisition(
            TimeSeries(
                name="GlucoseLevel",
                description="Raw current from Medtronic iPro2 ISIG tracking.",
                units="nA",
                data=H5DataIO(self.glucose_series.isig),  # should not need iterative write
                conversion=1.0,
                timestamps=H5DataIO(self.glucose_series.timestamps),
            ),
        )
