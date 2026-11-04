"""Epochs (sub-sessions) of a Valero session (DANDI:000568)."""

from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile

from .valeroutils import as_list, read_cell_metrics_session, read_session

EPOCH_COLUMNS = {
    "name": ("epoch_name", "name of the sub-session folder"),
    "behavioralParadigm": ("behavioral_paradigm", "the lab's label of the epoch (behavioralParadigm)"),
    "environment": ("environment", "where the mouse was (environment)"),
    "manipulation": ("manipulation", "stimulation in the epoch (manipulation)"),
    "notes": ("notes", "the lab's notes on the epoch"),
}


def same_epochs(epochs, other_epochs) -> bool:
    return len(epochs) == len(other_epochs) and all(
        epoch["name"] == other["name"] and abs(float(epoch["startTime"]) - float(other["startTime"])) < 1e-3
        for epoch, other in zip(epochs, other_epochs)
    )


class ValeroEpochsInterface(BaseDataInterface):
    """Epochs from session.mat, or from the copy of session.mat in cell_metrics when session.mat has names only."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        epochs = as_list(read_session(self.session_path)["epochs"])
        source = "session.mat"
        if not any("behavioralParadigm" in epoch for epoch in epochs):
            copy = read_cell_metrics_session(self.session_path)
            if copy is not None and same_epochs(epochs, as_list(copy["epochs"])):
                epochs = as_list(copy["epochs"])
                source = (
                    "the copy of session.mat saved in cell_metrics.cellinfo.mat (session.mat itself gives only the "
                    "epoch names)"
                )
        fields = [field for field in EPOCH_COLUMNS if any(field in epoch for epoch in epochs)]
        description = f"sub-sessions of the recording, from {source}"
        if "behavioralParadigm" not in fields:
            description += "; the source gives no label for the epochs"
        pulses_path = self.session_path / f"{self.session_id}.uLEDPulses.event.mat"
        if pulses_path.is_file():
            info = read_mat(str(pulses_path), variable_names=["uLEDPulses"])["uLEDPulses"].get("manipulationInfo", {})
            if info.get("effectorType") not in (None, "None"):
                description += (
                    f"; uLEDPulses.manipulationInfo gives effector {info['effectorType']} and injection of "
                    f"{info['injected']} at {float(info['manipulationTime']):.2f} s"
                )
        nwbfile.epochs = TimeIntervals(name="epochs", description=description)
        for field in fields:
            name, column_description = EPOCH_COLUMNS[field]
            nwbfile.add_epoch_column(name=name, description=column_description)
        for epoch in sorted(epochs, key=lambda epoch: float(epoch["startTime"])):
            row = {EPOCH_COLUMNS[field][0]: str(epoch.get(field, "")) for field in fields}
            nwbfile.add_epoch(start_time=float(epoch["startTime"]), stop_time=float(epoch["stopTime"]), **row)
