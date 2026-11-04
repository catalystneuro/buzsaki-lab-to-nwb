"""Conversion of the Petersen and Buzsaki 2020 sessions (DANDI:000059)."""

import uuid

from neuroconv import NWBConverter

from .petersenbehaviorinterface import PetersenBehaviorInterface
from .petersenecephysinterface import PetersenEcephysInterface
from .petersensortinginterface import PetersenSortingInterface
from .petersenutils import split_session_id

# Weights from the Buzsaki lab website, as in the earlier conversion
SUBJECT_WEIGHTS_KG = dict(MS10=0.395, MS12=0.410, MS13=0.320, MS21=0.250, MS22=0.260)


class PetersenNWBConverter(NWBConverter):
    """Primary conversion class for the Petersen and Buzsaki 2020 sessions."""

    # Ecephys first: it creates the electrodes
    data_interface_classes = dict(
        Ecephys=PetersenEcephysInterface,
        Sorting=PetersenSortingInterface,
        Behavior=PetersenBehaviorInterface,
    )

    def get_metadata(self):
        metadata = super().get_metadata()
        behavior = self.data_interface_objects["Behavior"]
        session_id = behavior.session_id
        subject_id, session_start_time = split_session_id(session_id)
        animal = behavior.session.get("animal", {})
        metadata["Subject"].update(
            subject_id=subject_id,
            description=(
                f"{animal.get('geneticLine', 'Wild type')} {animal.get('strain', 'Long Evans')} rat with silicon probes "
                "in the dorsal hippocampus and a cooling probe in the medial septum"
            ),
        )
        if subject_id in SUBJECT_WEIGHTS_KG:
            metadata["Subject"]["weight"] = f"{SUBJECT_WEIGHTS_KG[subject_id]} kg"
        epochs = behavior.session.get("epochs")
        epochs = [epochs] if isinstance(epochs, dict) else (epochs or [])
        paradigms = ", ".join(dict.fromkeys(str(epoch.get("behavioralParadigm")) for epoch in epochs))
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            session_start_time=session_start_time,
            session_description=(
                "Recording in CA1 of the dorsal hippocampus during the theta maze alternation task, with cooling of "
                "the medial septum, and in the home cage"
                + (f" (the lab's epochs: {paradigms})" if paradigms else "")
                + "."
            ),
        )
        return metadata
