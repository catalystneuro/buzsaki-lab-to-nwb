"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.utils import get_base_schema, get_schema_from_hdmf_class
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.behavior import SpatialSeries
import os
from copy import deepcopy
from pathlib import Path
from typing import Union
# TODO: there doesn't seem to be a pypi for to_nwb...
# we can always have them on our own end locally, but what about users?
from to_nwb.neuroscope import add_position_data

PathType = Union[str, Path, None]


class YutaPositionInterface(BaseDataInterface):

    @classmethod
    def get_input_schema(cls):
        return {}

    def __init__(self, **input_args):
        super().__init__(**input_args)

    def get_metadata_schema(self):
        metadata_schema = deepcopy(get_base_schema())

        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['SpatialSeries'] = get_schema_from_hdmf_class(SpatialSeries)
        required_fields = ['SpatialSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)

        return metadata_schema

    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict,
                     stub_test: bool = False):
        session_path = self.input_args['folder_path']
        subject_path, session_id = os.path.split(session_path)
        add_position_data(nwbfile, session_path)
