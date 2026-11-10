"""Conversion of the Valero et al. 2022 sessions (DANDI:000568)."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from neuroconv import NWBConverter
from neuroconv.utils import dict_deep_update, load_dict_from_file

from .behaviorinterface import (
    ValeroBehaviorLinearTrackInterface,
    ValeroBehaviorLinearTrackRewardsInterface,
)
from .ecephys_interface import ValeroEcephysInterface
from .epochsinterface import ValeroEpochsInterface, same_epochs
from .eventsinterface import (
    ValeroBehaviorSleepStatesInterface,
    ValeroHSEventsInterface,
    ValeroHSUPDownEventsInterface,
    ValeroRipplesEventsInterface,
)
from .sortinginterface import ValeroSortingInterface
from .stimulilaserinterface import ValeroULEDPulsesInterface
from .trialsinterface import ValeroTrialInterface
from .valeroutils import as_list, read_cell_metrics_session, read_session, session_date
from .videointerface import ValeroVideoInterface

# The paper: "CamKIIa-Cre::Ai32 mice (822 pyramidal neurons in four mice)"
PAPER_GENOTYPE = "CamkII/Ai32"


class ValeroNWBConverter(NWBConverter):
    """Primary conversion class for the Valero 2022 experiment."""

    # Ecephys first: it creates the electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=ValeroEcephysInterface,
        Sorting=ValeroSortingInterface,
        Epochs=ValeroEpochsInterface,
        Trials=ValeroTrialInterface,
        OptogeneticStimuli=ValeroULEDPulsesInterface,
        BehaviorLinearTrack=ValeroBehaviorLinearTrackInterface,
        BehaviorLinearTrackRewards=ValeroBehaviorLinearTrackRewardsInterface,
        BehaviorSleepStates=ValeroBehaviorSleepStatesInterface,
        RippleEvents=ValeroRipplesEventsInterface,
        HSEvents=ValeroHSEventsInterface,
        UPDownEvents=ValeroHSUPDownEventsInterface,
        Video=ValeroVideoInterface,
    )

    def __init__(self, source_data: dict, session_folder_path: str, verbose: bool = False):
        super().__init__(source_data=source_data, verbose=verbose)
        self.session_folder_path = Path(session_folder_path)
        self.session_id = self.session_folder_path.name

    def get_metadata(self):
        metadata = dict_deep_update(super().get_metadata(), load_dict_from_file(Path(__file__).parent / "metadata.yml"))
        session = read_session(self.session_folder_path)
        metadata["NWBFile"]["session_id"] = self.session_id
        metadata["NWBFile"]["session_start_time"] = datetime.combine(
            session_date(self.session_id), datetime.min.time(), tzinfo=ZoneInfo("America/New_York")
        )

        animal, notes = dict(session["animal"]), []
        if animal.get("species") != "Mouse":
            template_values = (
                f"species {animal.get('species')}, strain {animal.get('strain')}, genetic line "
                f"{animal.get('geneticLine')}"
            )
            copy = read_cell_metrics_session(self.session_folder_path)
            if (
                copy is not None
                and copy.get("animal", {}).get("species") == "Mouse"
                and same_epochs(as_list(session["epochs"]), as_list(copy["epochs"]))
            ):
                animal = dict(copy["animal"])
                notes.append(
                    f"session.mat gives {template_values}, the lab's template values; the subject fields are from "
                    "the copy of session.mat in cell_metrics.cellinfo.mat"
                )
            else:
                animal = dict(name=animal["name"], sex=animal.get("sex"), geneticLine=PAPER_GENOTYPE)
                notes.append(
                    f"session.mat gives {template_values}, the lab's template values; the genotype is the paper's "
                    "(all mice were CamKIIa-Cre::Ai32) and the strain is not known"
                )
        subject = metadata["Subject"]
        subject.update(subject_id=str(animal["name"]), sex=str(animal.get("sex", "U"))[0], age="/")
        subject["genotype"] = str(animal.get("geneticLine", PAPER_GENOTYPE))
        if animal.get("strain"):
            subject["strain"] = str(animal["strain"])
        surgery = animal.get("surgeries")
        if isinstance(surgery, dict):
            if np.size(surgery.get("weight")) == 1 and np.isfinite(float(surgery["weight"])):
                subject["weight"] = f"{float(surgery['weight']) / 1000:g} kg"
                notes.append(f"The weight ({float(surgery['weight']):g} g) is from the surgery record of session.mat")
            if isinstance(surgery.get("date"), str) and surgery["date"]:
                notes.append(f"The probe was implanted on {surgery['date']} (session.mat surgery record)")
        subject["description"] = subject.get("description", "") + "".join(f" {note}." for note in notes)
        subject["description"] += " The age of the mouse is not in the source."

        labels = [epoch.get("behavioralParadigm") for epoch in as_list(session["epochs"])]
        if labels and all(labels):
            epochs_text = "; epochs: " + ", ".join(str(label) for label in labels)
        else:
            epochs_text = ""
        metadata["NWBFile"]["session_description"] = (
            f"Chronic recording with a 4-shank uLED probe in CA1 of mouse {animal['name']} in the home cage and on a "
            f"linear track, with random pulses from the probe's 12 uLEDs{epochs_text}."
        )
        return metadata
