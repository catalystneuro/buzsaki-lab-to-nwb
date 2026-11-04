"""Authors: Cody Baker and Ben Dichter."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import FilePath
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.epoch import TimeIntervals

STATE_LABELS = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")


class WatsonSleepStatesInterface(BaseDataInterface):
    """Sleep states from the WAKEstate, NREMstate and REMstate intervals of a .SleepState.states.mat file."""

    def __init__(self, file_path: FilePath, verbose: bool = False):
        super().__init__(file_path=file_path, verbose=verbose)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        file_path = Path(self.source_data["file_path"])
        intervals = read_mat(str(file_path))["SleepState"]["ints"]

        table = TimeIntervals(
            name="sleep_states",
            description=f"Sleep states of the animal, from the WAKEstate, NREMstate and REMstate intervals of {file_path.name}.",
        )
        table.add_column(name="label", description="sleep state")
        rows = []
        for name, label in STATE_LABELS.items():
            for start_time, stop_time in np.reshape(intervals.get(name, []), (-1, 2)):
                rows.append(dict(start_time=float(start_time), stop_time=float(stop_time), label=label))
        for row in sorted(rows, key=lambda row: row["start_time"]):
            table.add_row(**row)

        get_module(nwbfile=nwbfile, name="behavior", description="behavioral states of the animal").add(table)
