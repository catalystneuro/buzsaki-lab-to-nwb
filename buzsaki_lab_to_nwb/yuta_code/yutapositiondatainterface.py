"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile

from ..neuroscope import add_position_data


class YutaPositionInterface(BaseDataInterface):
    """Interface for converting raw position data for the Yuta experiments (visual cortex)."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(folder_path=dict(type="string")))

    def run_conversion(self, nwbfile: NWBFile, metadata_dict: dict):
        session_path = self.source_data['folder_path']
        add_position_data(nwbfile, session_path)
