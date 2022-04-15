"""Author: Cody Baker."""
from pathlib import Path

from spikeextractors import RecordingExtractor, BinDatRecordingExtractor
from nwb_conversion_tools.utils import FilePathType
from pyintan import read_rhd

from .tingleyauxextractor import TingleyAuxExtractor


class TingleyMetabolicAuxExtractor(BinDatRecordingExtractor):
    """Aux data interface for the Tingley metabolic project."""

    RX = TingleyAuxExtractor

    extractor_name = "TingleyMetabolicAuxExtractor"
    has_default_locations = False
    has_unscaled = True
    is_writable = True
    mode = "file"

    def __init__(self, dat_file_path: FilePathType, rhd_file_path: FilePathType):
        dat_file_path = Path(dat_file_path)
        rhd_file_path = Path(rhd_file_path)

        RecordingExtractor.__init__(self)
        rhd_info = read_rhd(filename=self.source_data["rhd_file_path"])
        first_aux_entry = next(
            header_info_entry
            for header_info_entry in rhd_info[1]
            if header_info_entry["native_channel_name"] == "A-AUX1"
        )
        first_aux_sub_entry = next(
            header_info_entry for header_info_entry in rhd_info[2] if header_info_entry[0] == "A-AUX1"
        )

        # Manually confirmed that all aux channels have same properties
        gain = first_aux_entry["gain"]  # offset confirmed to be 0, units confirmed to be Volts
        sampling_frequency = first_aux_entry["sampling_rate"]
        dtype = first_aux_sub_entry[1]
        numchan = sum("AUX" in header_info_entry["native_channel_name"] for header_info_entry in rhd_info[1])

        BinDatRecordingExtractor.__init__(
            self,
            file_path=dat_file_path,
            sampling_frequency=sampling_frequency,
            dtype=dtype,
            numchan=numchan,
            gain=gain,
        )
        self._kwargs = dict(
            dat_file_path=str(Path(dat_file_path).absolute()), rhd_file_path=str(Path(rhd_file_path).absolute())
        )
