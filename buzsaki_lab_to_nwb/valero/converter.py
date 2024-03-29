from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
from neuroconv import NWBConverter
from pymatreader import read_mat
from pynwb import NWBFile

from buzsaki_lab_to_nwb.valero.behaviorinterface import (
    ValeroBehaviorLinearTrackInterface,
    ValeroBehaviorLinearTrackRewardsInterface,
)
from buzsaki_lab_to_nwb.valero.ecephys_interface import (
    ValeroLFPInterface,
    ValeroRawInterface,
)
from buzsaki_lab_to_nwb.valero.epochsinterface import ValeroEpochsInterface
from buzsaki_lab_to_nwb.valero.eventsinterface import (
    ValeroBehaviorSleepStatesInterface,
    ValeroHSEventsInterface,
    ValeroHSUPDownEventsInterface,
    ValeroRipplesEventsInterface,
)
from buzsaki_lab_to_nwb.valero.sortinginterface import CellExplorerSortingInterface
from buzsaki_lab_to_nwb.valero.stimulilaserinterface import (
    VeleroOptogeneticStimuliInterface,
)
from buzsaki_lab_to_nwb.valero.trialsinterface import ValeroTrialInterface
from buzsaki_lab_to_nwb.valero.videointerface import ValeroVideoInterface


class ValeroNWBConverter(NWBConverter):
    """Primary conversion class for the Valero 2022 experiment."""

    data_interface_classes = dict(
        Recording=ValeroRawInterface,
        LFP=ValeroLFPInterface,
        Sorting=CellExplorerSortingInterface,
        Video=ValeroVideoInterface,
        Trials=ValeroTrialInterface,
        Epochs=ValeroEpochsInterface,
        OptogeneticStimuli=VeleroOptogeneticStimuliInterface,
        BehaviorLinearTrack=ValeroBehaviorLinearTrackInterface,
        BehaviorSleepStates=ValeroBehaviorSleepStatesInterface,
        BehaviorLinearTrackRewards=ValeroBehaviorLinearTrackRewardsInterface,
        RippleEvents=ValeroRipplesEventsInterface,
        HSEvents=ValeroHSEventsInterface,
        UPDownEvents=ValeroHSUPDownEventsInterface,
    )

    def __init__(self, source_data: dict, session_folder_path: str, verbose: bool = True):
        super().__init__(source_data=source_data, verbose=verbose)

        self.session_folder_path = Path(session_folder_path)
        self.session_id = self.session_folder_path.stem

    def get_metadata(self):
        metadata = super().get_metadata()
        session_file_path = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file_path.is_file(), f"Session file not found: {session_file_path}"

        ignore_fields = ["behavioralTracking", "timeSeries", "spikeSorting", "extracellular", "brainRegions"]
        session_mat = read_mat(session_file_path, ignore_fields=ignore_fields)
        session_data = session_mat["session"]

        # Add session start time
        date = session_data["general"]["date"]  # This does not contain the time
        date = datetime.strptime(date, "%Y-%m-%d")  # Conver date str to date object

        tzinfo = ZoneInfo("America/New_York")
        session_start_time = datetime.combine(date, datetime.min.time(), tzinfo=tzinfo)
        metadata["NWBFile"]["session_start_time"] = session_start_time

        session_name = session_data["general"]["name"]
        metadata["NWBFile"]["session_id"] = session_name

        # Add subject metadata
        subject_data = session_data["animal"]
        subject_id = subject_data["name"]
        sex = subject_data["sex"]
        strain = subject_data["strain"]
        genotype = subject_data["geneticLine"]

        metadata["Subject"]["subject_id"] = subject_id
        metadata["Subject"]["sex"] = sex[0]  # This is Male or Female so first letter is M or F
        metadata["Subject"]["strain"] = strain
        metadata["Subject"]["genotype"] = genotype

        # Add weight if available
        if "surgeries" in subject_data:  # TODO: subjects are repeated, maybe the only added weight info in one of them
            surgeries_data = subject_data["surgeries"]
            weight_in_grams = surgeries_data["weight"]
            metadata["Subject"]["weight"] = f"{weight_in_grams / 1000:2.3f} kg"  # Convert to kg

        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None):
        conversion_options = conversion_options or dict()
        for interface_name, data_interface in self.data_interface_objects.items():
            print(f"Adding {interface_name} to NWBFile...")
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **conversion_options.get(interface_name, dict())
            )
