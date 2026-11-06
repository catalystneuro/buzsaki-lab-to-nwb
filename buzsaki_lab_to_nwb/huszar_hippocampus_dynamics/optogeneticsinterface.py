"""Light pulses for optogenetic tagging in a Huszar session (DANDI:000552), from pulses.events.mat."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pydantic import DirectoryPath
from pymatreader import read_mat
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile


class HuszarOptogeneticPulsesInterface(BaseDataInterface):
    """Each light pulse as an interval, and the periods of pulse trains the lab marked (intsPeriods).

    The paper tags the birthdated CA1 pyramidal neurons with light: they express an opsin delivered by in utero
    electroporation.
    """

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        pulses = read_mat(self.session_path / f"{self.session_id}.pulses.events.mat")["pulses"]
        times = np.atleast_2d(np.asarray(pulses["timestamps"], dtype=float))
        amplitude = np.atleast_1d(pulses["amplitude"])
        event_id = np.atleast_1d(pulses["eventID"])

        table = TimeIntervals(
            name="OptogeneticPulses",
            description=(
                "light pulses for optogenetic tagging, as detected by the lab (pulses.events.mat timestamps); "
                "start and stop of each pulse"
            ),
        )
        table.add_column(
            name="amplitude",
            description="pulse amplitude as detected by the lab (pulses.events.mat amplitude); its unit is not given",
        )
        table.add_column(
            name="event_id", description="the lab's pulse type (pulses.events.mat eventID); its meaning is not given"
        )
        for (start_time, stop_time), value, identifier in zip(times, amplitude, event_id):
            table.add_row(
                start_time=float(start_time),
                stop_time=float(stop_time),
                amplitude=float(value),
                event_id=int(identifier),
            )
        nwbfile.add_time_intervals(table)

        periods = np.asarray(pulses.get("intsPeriods", []), dtype=float).reshape(-1, 2)
        if len(periods):
            period_table = TimeIntervals(
                name="OptogeneticPulsePeriods",
                description="periods of light pulse trains, as marked by the lab (pulses.events.mat intsPeriods)",
            )
            for start_time, stop_time in periods:
                period_table.add_row(start_time=float(start_time), stop_time=float(stop_time))
            nwbfile.add_time_intervals(period_table)
