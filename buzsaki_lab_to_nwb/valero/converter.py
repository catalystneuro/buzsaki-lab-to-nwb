from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from scipy.io import loadmat as loadmat_scipy

from neuroconv import NWBConverter
from neuroconv.datainterfaces import NeuroScopeRecordingInterface, NeuroScopeLFPInterface

from buzsaki_lab_to_nwb.valero.sortinginterface import CellExplorerSortingInterface


class ValeroNWBConverter(NWBConverter):
    """Primary conversion class for the Valero 2022 experiment."""

    data_interface_classes = dict(
        Recording=NeuroScopeRecordingInterface,
        LFP=NeuroScopeLFPInterface,
        Sorting=CellExplorerSortingInterface,
    )

    def __init__(self, source_data: dict, verbose: bool = True):
        super().__init__(source_data=source_data, verbose=verbose)

        self.session_folder_path = Path(self.data_interface_objects["Recording"].source_data["file_path"]).parent
        self.session_id = self.session_folder_path.stem

    def get_metadata(self):
        metadata = super().get_metadata()
        session_file = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file.is_file(), f"Session file not found: {session_file}"

        session_mat = loadmat_scipy(session_file, simplify_cells=True)
        date = session_mat["session"]["general"]["date"]  # This does not contain the time
        # Conver date str to date object
        date = datetime.strptime(date, "%Y-%m-%d")
        # Build a datetime object and add the timezone from NY
        date = datetime.combine(date, datetime.min.time())
        tzinfo = ZoneInfo("America/New_York")  # This is the standard library
        date = date.replace(tzinfo=tzinfo)

        # Get today date
        metadata["NWBFile"]["session_start_time"] = date
        return metadata
