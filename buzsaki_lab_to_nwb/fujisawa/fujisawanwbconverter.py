"""Conversion of the Fujisawa et al. 2008 sessions (DANDI:000067)."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .fujisawabehaviorinterface import FujisawaBehaviorInterface
from .fujisawaecephysinterface import FujisawaEcephysInterface
from .fujisawasortinginterface import FujisawaSortingInterface
from .fujisawautils import SESSIONS, subject_of

# Recording years: the raw EE.dat of EE.188 is dated 2006-07-14, six days after its folder date (07/08). The year of
# rats FF and GG is not recorded in the source; theirs is kept as in the earlier conversion.
YEARS = {"EE": 2006, "FF": 2008, "GG": 2008}
SESSION_DESCRIPTIONS = {
    "sleep": "Sleep in the home cage.",
    "test": "A short test recording.",
    "spontaneous alternation task": "Spontaneous alternation task in the maze, with a running wheel.",
    "working memory task": (
        "Working memory task in the maze: each trial starts with nose pokes in the start area and ends with the reward "
        "in the left or right side arm."
    ),
}


class FujisawaNWBConverter(NWBConverter):
    """Primary conversion class for the Fujisawa et al. 2008 sessions."""

    # Ecephys first: it creates the electrode groups the units refer to
    data_interface_classes = dict(
        Ecephys=FujisawaEcephysInterface,
        Sorting=FujisawaSortingInterface,
        Behavior=FujisawaBehaviorInterface,
    )

    def get_metadata(self):
        metadata = super().get_metadata()
        session_id = self.data_interface_objects["Ecephys"].session_id
        subject = subject_of(session_id)
        day, state, duration = SESSIONS[session_id]
        date = datetime(YEARS[subject], int(day[2:4]), int(day[4:6]), tzinfo=ZoneInfo("America/New_York"))
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid5(uuid.NAMESPACE_URL, f"DANDI:000067/{session_id}")),
            session_start_time=date,
            session_description=(
                f"{SESSION_DESCRIPTIONS[state]} Session {session_id} of rat {subject}, recorded on {day[2:4]}/{day[4:6]} "
                f"({duration} min). The time of day is not recorded in the source, so the start time is midnight of "
                "the recording day."
            ),
        )
        metadata["Subject"] = dict(
            subject_id=subject,
            species="Rattus norvegicus",
            sex="M",
            age="P3M/P5M",
            description="male rat, 3 to 5 months old (as in the earlier conversion)",
        )
        return metadata
