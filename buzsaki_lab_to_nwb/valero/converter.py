from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    NeuroScopeLFPInterface,
    NeuroScopeRecordingInterface,
    VideoInterface,
)
from neuroconv.utils import FilePathType
from pymatreader import read_mat

from buzsaki_lab_to_nwb.valero.behaviorinterface import (
    ValeroBehaviorLinearTrackInterface,
    ValeroBehaviorLinearTrackRewardsInterface,
    ValeroBehaviorSleepStatesInterface,
)
from buzsaki_lab_to_nwb.valero.epochsinterface import ValeroEpochsInterface
from buzsaki_lab_to_nwb.valero.eventsinterface import (
    ValeroHSEventsInterface,
    ValeroHSUPDownEventsInterface,
    ValeroRipplesEventsInterface,
)
from buzsaki_lab_to_nwb.valero.sortinginterface import CellExplorerSortingInterface
from buzsaki_lab_to_nwb.valero.stimulilaserinterface import (
    VeleroOptogeneticStimuliInterface,
)
from buzsaki_lab_to_nwb.valero.trialsinterface import ValeroTrialInterface


class ValeroLFPExtractor(NeuroScopeLFPInterface):
    def __init__(
        self,
        file_path: FilePathType,
        gain: Optional[float] = None,
        xml_file_path: Optional[FilePathType] = None,
    ):
        super().__init__(file_path, gain, xml_file_path)
        self.recording_extractor._sampling_frequency = 1250.0

        # Update the sampling frequency of the segments
        for segment in self.recording_extractor._recording_segments:
            segment.sampling_frequency = 1250.0


class ValeroNWBConverter(NWBConverter):
    """Primary conversion class for the Valero 2022 experiment."""

    data_interface_classes = dict(
        Recording=NeuroScopeRecordingInterface,
        LFP=ValeroLFPExtractor,
        Sorting=CellExplorerSortingInterface,
        Video=VideoInterface,
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

    def __init__(self, source_data: dict, verbose: bool = True):
        super().__init__(source_data=source_data, verbose=verbose)

        self.session_folder_path = Path(self.data_interface_objects["Recording"].source_data["file_path"]).parent
        self.session_id = self.session_folder_path.stem

    def get_metadata(self):
        metadata = super().get_metadata()
        session_file = self.session_folder_path / f"{self.session_id}.session.mat"
        assert session_file.is_file(), f"Session file not found: {session_file}"

        session_mat = read_mat(session_file)
        session_data = session_mat["session"]

        # Add session start time
        date = session_data["general"]["date"]  # This does not contain the time
        date = datetime.strptime(date, "%Y-%m-%d")  # Conver date str to date object

        tzinfo = ZoneInfo("America/New_York")
        session_start_time = datetime.combine(date, datetime.min.time(), tzinfo=tzinfo)
        metadata["NWBFile"]["session_start_time"] = session_start_time

        session_name = session_data["general"]["sessionName"]
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

        surgeries_data = subject_data["surgeries"]
        weight_in_grams = surgeries_data["weight"]

        metadata["Subject"]["weight"] = f"{weight_in_grams / 1000:2.3f} kg"  # Convert to kg

        return metadata
