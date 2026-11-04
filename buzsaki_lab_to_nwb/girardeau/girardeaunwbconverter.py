"""Conversion of the Girardeau et al. 2017 sessions (DANDI:000061)."""

import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .girardeaubehaviorinterface import GirardeauBehaviorInterface
from .girardeauecephysinterface import GirardeauEcephysInterface
from .girardeausortinginterface import GirardeauSortingInterface
from .girardeauutils import load_mat, split_session_id


class GirardeauNWBConverter(NWBConverter):
    """Primary conversion class for the Girardeau et al. 2017 sessions."""

    # Ecephys first: it creates the electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=GirardeauEcephysInterface,
        Sorting=GirardeauSortingInterface,
        Behavior=GirardeauBehaviorInterface,
    )

    def get_metadata(self):
        metadata = super().get_metadata()
        session_path = Path(self.data_interface_objects["Behavior"].source_data["folder_path"])
        session_id = session_path.name
        rat, date = split_session_id(session_id)

        subject = dict(subject_id=rat, species="Rattus norvegicus", strain="Long-Evans", genotype="wild type")
        description = "Rat implanted with silicon probes in the amygdala on both sides and in the dorsal hippocampus."
        session_mat_path = session_path / f"{session_id}.session.mat"
        if session_mat_path.is_file():
            animal = load_mat(session_mat_path)["session"].animal
            sex = {"Male": "M", "Female": "F"}.get(str(animal.sex), "U")
            subject.update(sex=sex)
            description += (
                f" The lab's session.mat gives sex '{animal.sex}', strain '{animal.strain}' and genetic line "
                f"'{animal.geneticLine}'."
            )
        else:
            subject.update(sex="U")
        # The earlier DANDI files give every rat an age of 3 months (and 300 g); the lab's files on the share give no
        # age, so that value is kept, as the paper's
        subject.update(age="P3M")
        description += (
            " Age: 3 months, the value of the earlier DANDI:000061 files, not found in the lab's files (the source of "
            "that value is not known); weight is not given per rat."
        )
        subject.update(description=description)
        metadata["Subject"].update(subject)
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            # The source gives only the date
            session_start_time=date.replace(tzinfo=ZoneInfo("America/New_York")),
            session_description=(
                "One recording day: linear track running before training (prerun), home-cage sleep (presleep), "
                "training on the linear track with an air puff in one running direction (run), home-cage sleep "
                "(postsleep) and running after training (postrun), recorded as one concatenated session. The start "
                "time of the day is not in the source, so session_start_time is midnight of the recording date."
            ),
        )
        return metadata
