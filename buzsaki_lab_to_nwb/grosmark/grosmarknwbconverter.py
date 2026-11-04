"""Conversion of the Grosmark and Buzsaki 2016 sessions (DANDI:000044)."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .grosmarkbehaviorinterface import GrosmarkBehaviorInterface
from .grosmarkecephysinterface import GrosmarkEcephysInterface
from .grosmarksortinginterface import GrosmarkSortingInterface
from .grosmarkutils import MAZE_DESCRIPTIONS, read_sess_info, recording_start, split_session_id


class GrosmarkNWBConverter(NWBConverter):
    """Primary conversion class for the Grosmark and Buzsaki 2016 sessions."""

    # Ecephys first: it creates the electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=GrosmarkEcephysInterface,
        Sorting=GrosmarkSortingInterface,
        Behavior=GrosmarkBehaviorInterface,
    )

    def __init__(self, source_data: dict, meta_file_path: Optional[Path] = None, verbose: bool = False):
        """`meta_file_path` is the Amplipex .meta file of the session's PRE recording, which gives its start time."""
        super().__init__(source_data=source_data, verbose=verbose)
        self.meta_file_path = meta_file_path

    def get_metadata(self):
        metadata = super().get_metadata()
        session_path = self.data_interface_objects["Behavior"].session_path
        session_id = session_path.name
        rat, date = split_session_id(session_id)
        maze_type = read_sess_info(session_path / f"{session_id}_sessInfo.mat")["maze_type"]

        metadata["Subject"].update(
            subject_id=rat,
            species="Rattus norvegicus",
            strain="Long-Evans",
            sex="M",
            genotype="wild type",
            description=(
                "Male Long-Evans rat, 250-350 g, implanted with two silicon probes in the dorsal CA1 of both "
                "hemispheres. The lab did not record its date of birth or age, nor its weight on the recording day."
            ),
        )

        start = recording_start(self.meta_file_path)
        if start is not None and start.date() != date.date():
            raise ValueError(f"{self.meta_file_path} is not a recording of {session_id}")
        start_note = (
            " The session start time is the start of the PRE recording, from its Amplipex .meta file."
            if start is not None
            else " The time of day the session started is not recorded; the start time is midnight of the session date."
        )
        session_start_time = (start or datetime.combine(date.date(), datetime.min.time())).replace(
            tzinfo=ZoneInfo("America/New_York")
        )
        session_description = (
            f"Rat {rat}: a long PRE rest/sleep epoch in the home cage, a novel MAZE epoch running on "
            f"{MAZE_DESCRIPTIONS.get(maze_type, maze_type)} ('{maze_type}') in a novel room, then a long POST rest/sleep "
            "epoch in the home cage, with LFP and units from two silicon probes in the CA1 pyramidal layer of both "
            "hemispheres, neck EMG and a head-mounted accelerometer. The three recordings were concatenated by the lab, "
            "so all times are seconds into the concatenated recording." + start_note
        )
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            session_start_time=session_start_time,
            session_description=session_description,
        )
        return metadata
