from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.json_schema import FolderPathType
from pymatreader import read_mat
from pynwb.file import NWBFile


class ValeroEpochsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        session_file_path = self.session_path / f"{self.session_id}.session.mat"
        assert session_file_path.is_file(), session_file_path
        mat_file = read_mat(session_file_path)

        epoch_list = mat_file["session"]["epochs"]

        nwbfile.add_epoch_column(name="behavioral_paradigm", description="The behavioral paradigm of the epoch")
        nwbfile.add_epoch_column(name="environment", description="The environment in the epoch")
        nwbfile.add_epoch_column(name="manipulation", description="The stimulus in the epoch")

        for epoch in epoch_list:
            start_time = float(epoch["startTime"])
            stop_time = float(epoch["stopTime"])
            behavioral_paradigm = epoch["behavioralParadigm"]
            environment = epoch["environment"]
            manipulation = epoch["manipulation"]

            nwbfile.add_epoch(
                start_time=start_time,
                stop_time=stop_time,
                behavioral_paradigm=behavioral_paradigm,
                environment=environment,
                manipulation=manipulation,
            )
