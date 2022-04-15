"""Authors: Heberto Mayorquin and Cody Baker."""
from nwb_conversion_tools.basedatainterface import BaseRecordingDataInterface
from nwb_conversion_tools.utils import FilePathType

from .tingleyauxextractor import TingleyAuxExtractor


class TingleyMetabolicAuxInterface(BaseRecordingDataInterface):
    """Aux data interface for the Tingley metabolic project."""

    RX = TingleyAuxExtractor

    def __init__(self, dat_file_path: FilePathType, rhd_file_path: FilePathType):
        super().__init__(dat_file_path=dat_file_path, rhd_file_path=rhd_file_path)
