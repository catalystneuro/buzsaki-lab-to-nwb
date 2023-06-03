from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils.json_schema import FolderPathType
from pynwb.file import NWBFile
from pymatreader import read_mat


class HuszarEpochsInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        self.session_path = Path(self.source_data["folder_path"])
        self.session_id = self.session_path.stem

        session_file_path = self.session_path / f"{self.session_id}.session.mat"
        assert session_file_path.is_file(), session_file_path
        mat_file = read_mat(session_file_path)

        epoch_list = mat_file["session"]["epochs"]

        for epoch in epoch_list:
            start_time = float(epoch["startTime"])
            stop_time = float(epoch["stopTime"])

            nwbfile.add_epoch(start_time=start_time, stop_time=stop_time)
