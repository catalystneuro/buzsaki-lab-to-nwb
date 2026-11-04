"""Conversion of the Peyrache et al. 2015 sessions (DANDI:000056, CRCNS th-1)."""

import uuid
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .peyracheecephysinterface import PeyracheEcephysInterface
from .peyrachebehaviorinterface import PeyracheBehaviorInterface
from .peyrachesortinginterface import PeyracheSortingInterface
from .peyracheutils import read_session_xml, split_session_id

# Sessions with a note in their description; the data are kept as the lab gives them
SESSION_NOTES = {
    "Mouse12-120808": (
        " The lab left this session out of its list of AD sessions (datasets_Adn.list). Its position and spikes do not "
        "share a clock in sub-recording 03 (see the position series), and its 'wake' epoch is the second "
        "environment (see the epochs)."
    ),
    "Mouse32-140820": " This session is not in the CRCNS th-1 session table nor in the lab's session lists.",
}


class PeyracheNWBConverter(NWBConverter):
    """Primary conversion class for the Peyrache et al. 2015 sessions."""

    # Ecephys first: it creates the electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=PeyracheEcephysInterface,
        Sorting=PeyracheSortingInterface,
        Behavior=PeyracheBehaviorInterface,
    )

    def get_metadata(self):
        metadata = super().get_metadata()
        ecephys = self.data_interface_objects["Ecephys"]
        session_id = ecephys.session_id
        mouse, date = split_session_id(session_id)
        xml_info = read_session_xml(ecephys.session_path / f"{session_id}.xml")
        regions = set(ecephys.regions.values())
        sites = "the anterior thalamus and the post-subiculum" if "postsub" in regions else "the anterior thalamus"
        session_description = (
            f"Recording from {sites} of a freely moving mouse: sleep in the home cage before and after foraging for "
            "food in an open field (53 x 46 cm)."
        ) + SESSION_NOTES.get(session_id, "")
        metadata["Subject"].update(
            subject_id=mouse,
            species="Mus musculus",
            sex="U",
            age="/",  # not in the source or the paper
            description=(
                "Adult mouse (27-50 g). The paper used five male and two female mice but does not say which mouse is "
                "which, so the sex of each is not known."
            ),
        )
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            session_start_time=date.replace(tzinfo=ZoneInfo("America/New_York")),
            session_description=session_description,
            notes="Description of the recording in the session's .xml file (by the lab):\n" + xml_info["description"],
        )
        return metadata
