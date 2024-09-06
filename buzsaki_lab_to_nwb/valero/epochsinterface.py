import warnings
from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.file import NWBFile


class ValeroEpochsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        session_file_path = self.session_path / f"{self.session_id}.session.mat"

        mat_file = read_mat(session_file_path)

        epoch_list = mat_file["session"]["epochs"]

        # Probe for field availability
        first_epoch = epoch_list[0]
        available_fields = list(first_epoch.keys())
        available_fields.remove("startTime")
        available_fields.remove("stopTime")

        # Maps the name found in the mat file to the name and description in the NWB file
        epoch_description = {
            "name": dict(name="epoch_name", description="The name of the epoch"),
            "behavioralParadigm": dict(name="behavioral_paradigm", description="The behavioral paradigm of the epoch"),
            "environment": dict(name="environment", description="The environment in the epoch"),
            "manipulation": dict(name="manipulation", description="The stimulus in the epoch"),
        }
        for field in available_fields:
            name = epoch_description[field]["name"]
            description = epoch_description[field]["description"]
            nwbfile.add_epoch_column(name=name, description=description)

        for epoch in epoch_list:
            start_time = float(epoch["startTime"])
            stop_time = float(epoch["stopTime"])

            extra_kwargs = {epoch_description[field]["name"]: epoch[field] for field in available_fields}

            nwbfile.add_epoch(start_time=start_time, stop_time=stop_time, **extra_kwargs)
