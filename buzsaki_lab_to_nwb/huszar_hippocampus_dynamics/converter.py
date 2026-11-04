"""Conversion of the Huszar et al. 2022 sessions (DANDI:000552)."""

import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .behaviorinterface import (
    HuszarBehavior8MazeRewardsInterface,
    HuszarPositionInterface,
    HuzsarBehaviorSleepInterface,
)
from .ecephysinterface import HuszarEcephysInterface
from .epochsinterface import HuszarEpochsInterface
from .huszarutils import birthdate_from_subject_id, read_maze_info, read_session, sex_from_subject_id
from .optogeneticsinterface import HuszarOptogeneticPulsesInterface
from .ripplesinterface import HuszarProcessingRipplesEventsInterface
from .sortinginterface import HuszarSortingInterface
from .trialsinterface import HuszarTrialsInterface

# Files of the 2023 conversion source that the Globus copy may lack, with what the earlier DANDI version had
SOURCE_GAPS = {
    "ripples.events.mat": "the lab's ripple detections (ripples.events.mat), which the 2023 version of this file has",
    "spikes.cellinfo.mat": "the lab's spike sorting (spikes.cellinfo.mat)",
}


class HuzsarNWBConverter(NWBConverter):
    """Primary conversion class for the Huszar hippocampus data set."""

    # Ecephys first: it creates the electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=HuszarEcephysInterface,
        Sorting=HuszarSortingInterface,
        Position=HuszarPositionInterface,
        BehaviorSleep=HuzsarBehaviorSleepInterface,
        BehaviorRewards=HuszarBehavior8MazeRewardsInterface,
        Epochs=HuszarEpochsInterface,
        Trials=HuszarTrialsInterface,
        RippleEvents=HuszarProcessingRipplesEventsInterface,
        OptogeneticPulses=HuszarOptogeneticPulsesInterface,
    )

    def __init__(self, source_data: dict, verbose: bool = False):
        super().__init__(source_data=source_data, verbose=verbose)
        self.session_folder_path = Path(self.data_interface_objects["Epochs"].source_data["folder_path"])
        self.session_id = self.session_folder_path.name

    def get_metadata(self):
        metadata = super().get_metadata()
        session = read_session(self.session_folder_path)

        # The session id holds the date; session.mat general.date and the .xml date (2011-08-18) are template values
        date = datetime.strptime("20" + self.session_id.split("_")[2], "%Y%m%d")
        metadata["NWBFile"]["session_start_time"] = date.replace(tzinfo=ZoneInfo("America/New_York"))
        metadata["NWBFile"]["session_id"] = self.session_id
        metadata["NWBFile"]["identifier"] = str(uuid.uuid4())

        notes = []
        possible_note = str(session["general"].get("notes", ""))
        if (
            possible_note.replace("Notes:", "")
            .replace("Description from xml:", "")
            .replace("Notes from xml:", "")
            .replace("Description:", "")
            .strip()
        ):
            notes.append(possible_note)
        missing = [
            description
            for suffix, description in SOURCE_GAPS.items()
            if not (self.session_folder_path / f"{self.session_id}.{suffix}").is_file()
        ]
        if missing:
            notes.append(
                "Converted from the Buzsaki lab's Globus share (HuszarR/optotagCA1), which differs from the copy "
                "converted in 2023. Not in that source for this session: " + "; ".join(missing) + "."
            )
        if (
            not (self.session_folder_path / f"{self.session_id}.cell_metrics.cellinfo.mat").is_file()
            and (self.session_folder_path / f"{self.session_id}.spikes.cellinfo.mat").is_file()
        ):
            notes.append(
                "The session has no cell_metrics.cellinfo.mat in the source, so the units have no putative cell type "
                "or optogenetic tagging statistics."
            )
        if notes:
            metadata["NWBFile"]["notes"] = " ".join(notes)

        maze_info = read_maze_info(self.session_folder_path)
        has_behavior = (self.session_folder_path / f"{self.session_id}.Behavior.mat").is_file()
        description = (
            f"Recording from a {int(session['extracellular']['nChannels'])}-channel silicon probe in CA1, with light "
            "pulses for optogenetic tagging of the birthdated pyramidal neurons, "
        )
        if maze_info:
            description += "in the home cage and in these environments: " + ", ".join(maze_info) + " (maze_info.mat)."
        elif has_behavior:
            description += "in the home cage and in the spatial alternation task of the figure-8 maze."
        else:
            description += "in the home cage."
        metadata["NWBFile"]["session_description"] = description

        subject_id = "_".join(self.session_id.split("_")[:2])
        animal = session.get("animal", {})
        birthdate = birthdate_from_subject_id(subject_id)
        metadata["Subject"].update(
            subject_id=subject_id,
            sex=sex_from_subject_id(subject_id),
            strain=animal.get("strain", "C57BL/6"),
            genotype=animal.get("geneticLine", "Wild type"),
            description=(
                f"CA1 pyramidal neurons birthdated by in utero electroporation at {birthdate} (the e-number of the "
                "subject id; the source has no other record of the electroporation day). Sex from the m or f of the "
                "subject id."
            ),
        )
        # The source gives no age; the paper gives 3 to 6 months for the implanted mice as a group
        if "age" in animal:
            metadata["Subject"]["age"] = str(animal["age"])
        return metadata
