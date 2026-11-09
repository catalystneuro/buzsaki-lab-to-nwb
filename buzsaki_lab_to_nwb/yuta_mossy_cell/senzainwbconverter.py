"""Conversion of the Senzai and Buzsaki 2017 sessions (DANDI:000003)."""

import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from neuroconv import NWBConverter

from .senzaibehaviorinterface import SenzaiBehaviorInterface
from .senzaiecephysinterface import SenzaiEcephysInterface
from .senzaimonosynapticinterface import SenzaiMonosynapticInterface
from .senzaisortinginterface import SenzaiSortingInterface
from .senzaiutils import read_exp_sheet, read_unit_summary, split_session_id

# Mice whose experiment sheet and the flags of the lab's unit summary disagree on the genotype; the paper counts
# 7 SST-Cre, 3 POMC-Cre::Ai35, 5 DRD2-Cre::Ai35 and 1 wild-type mouse, which the summary matches for the paper's mice
# (YM21, SST-Cre, is not in the dandiset; YutaMouse57 is not in the paper)
# Where the paper settles the disagreement, its genotype is used
GENOTYPE_FROM_PAPER = {"YutaMouse41": "wild type"}
GENOTYPE_NOTES = {
    "YutaMouse39": "The experiment sheet gives no genotype; the lab's unit summary marks this mouse as SST-Cre.",
    "YutaMouse41": (
        "Wild type, as the lab's unit summary and the paper's one wild-type mouse (Table S1) have it; the experiment "
        "sheet gives POMC-Cre::Arch."
    ),
    "YutaMouse57": (
        "The experiment sheet gives POMC-Cre::Ai35, but the lab's unit summary marks this mouse as a DRD2-Cre::Ai35 "
        "mouse."
    ),
}


def normalize_genotype(genotype: str) -> str:
    """The sheets name the Ai35 (Rosa-CAG-LSL-Arch-GFP) reporter either Ai35 or Arch."""
    return genotype.replace("::Arch", "::Ai35").replace("Drd2", "DRD2")


class SenzaiNWBConverter(NWBConverter):
    """Primary conversion class for the Senzai and Buzsaki 2017 sessions."""

    # Ecephys first: it creates the electrodes that the units refer to; Sorting before the pairs that refer to units
    data_interface_classes = dict(
        Ecephys=SenzaiEcephysInterface,
        Sorting=SenzaiSortingInterface,
        Monosynaptic=SenzaiMonosynapticInterface,
        Behavior=SenzaiBehaviorInterface,
    )

    def __init__(self, source_data: dict, exp_sheet_folder_path: Path, verbose: bool = False):
        super().__init__(source_data=source_data, verbose=verbose)
        self.exp_sheet_folder_path = Path(exp_sheet_folder_path)

    def get_metadata(self):
        metadata = super().get_metadata()
        sorting = self.data_interface_objects["Sorting"]
        session_id = sorting.session_id
        mouse, date, second_session = split_session_id(session_id)
        number = mouse.removeprefix("YutaMouse")

        sheet = read_exp_sheet(self.exp_sheet_folder_path / f"YM{number} exp_sheet.xlsx")
        genotype = GENOTYPE_FROM_PAPER.get(mouse, sheet.get("genotype"))
        if not isinstance(genotype, str):
            summary = read_unit_summary(Path(sorting.source_data["unit_summary_file_path"]))
            flags = summary[summary.fname == session_id][["sstmouse", "pomcmouse", "drd2mouse", "wtmouse"]].max()
            genotype = {
                "sstmouse": "SST-Cre",
                "pomcmouse": "POMC-Cre::Ai35",
                "drd2mouse": "DRD2-Cre::Ai35",
                "wtmouse": "wild type",
            }[flags.idxmax()]
        description = "Male mouse implanted with a silicon probe in the dorsal hippocampus."
        if mouse in GENOTYPE_NOTES:
            description += " " + GENOTYPE_NOTES[mouse]

        subject = dict(
            subject_id=mouse,
            species="Mus musculus",
            sex="M",
            genotype=normalize_genotype(genotype),
            description=description,
        )
        birth = sheet.get("DOB")
        if isinstance(birth, pd.Timestamp) or hasattr(birth, "year"):
            subject["age"] = f"P{(date - pd.Timestamp(birth).to_pydatetime()).days}D"
        else:
            subject["age"] = "/"  # ISO 8601 for an unknown interval: the experiment sheet has no date of birth
        metadata["Subject"].update(subject)

        session_description = (
            "Recording in the home cage, the circular T-maze or an open field, from a silicon probe in the dentate "
            "gyrus and CA3."
        )
        if second_session:
            session_description += (
                " This is the second recording session of the day (named with 'b'), recorded with the same probe."
            )
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            session_start_time=date.replace(tzinfo=ZoneInfo("America/New_York")),
            session_description=session_description,
        )
        return metadata
