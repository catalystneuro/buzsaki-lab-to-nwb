"""Conversion of the Tingley and Buzsaki 2018 and 2020 sessions (DANDI:000213, DANDI:000218)."""

import uuid
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .tingleybehaviorinterface import TingleyBehaviorInterface, read_behavior
from .tingleyecephysinterface import TingleyEcephysInterface
from .tingleyeventsinterface import TingleyEventsInterface
from .tingleysortinginterface import TingleySortingInterface
from .tingleyutils import REGION_NAMES, merged_session_start, split_session_id


class TingleyNWBConverter(NWBConverter):
    """Primary conversion class for the Tingley lateral septum sessions."""

    # Ecephys first: it creates the electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=TingleyEcephysInterface,
        Sorting=TingleySortingInterface,
        Behavior=TingleyBehaviorInterface,
        Events=TingleyEventsInterface,
    )

    def get_metadata(self):
        metadata = super().get_metadata()
        ecephys = self.data_interface_objects["Ecephys"]
        session_path, session_id = ecephys.session_path, ecephys.session_id
        rat = session_path.parent.name
        name = split_session_id(session_id)

        start = name["start"]
        if start is not None:
            start_note = "The session start time is the start of the recording, from the session name."
        elif name["merged"] and merged_session_start(session_path) is not None:
            start = merged_session_start(session_path)
            start_note = (
                "The lab merged the session's recordings into one; the session start time is the start of the first "
                "recording, from the names of the recording folders."
            )
        else:
            start = name["date"]
            start_note = "The time of day the session started is not recorded; the start time is midnight of its date."

        probes = ecephys.probes()
        probe_text = " and ".join(
            f"one in the {REGION_NAMES.get(region, region)} ('{region}')"
            for _, region, _ in probes
            if region != "unknown"
        )
        depths = name["depths"]
        session_info = ecephys.session_info or {}
        depth_text = (
            f" The session name carries the depths {' and '.join(f'{depth} um' for depth in depths)}"
            + (f" (sessionInfo.depth is {session_info['depth']:g}, the first)" if session_info.get("depth") else "")
            + "; which probe each depth belongs to and what it is measured from are not stored in the source."
            if depths
            else ""
        )
        task = ""
        behavior_file_path = session_path / f"{session_id}.behavior.mat"
        if behavior_file_path.is_file():
            behavior = read_behavior(behavior_file_path)
            task = f" Task: {behavior['description']} ({len(behavior['intervals'])} trials)."
        session_description = (
            f"Rat {rat}, recorded with two silicon probes in the right hemisphere"
            + (f", {probe_text}" if probe_text else "")
            + ", in the home cage before and after running on a maze."
            + task
            + depth_text
            + " "
            + start_note
        )
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            session_start_time=start.replace(tzinfo=ZoneInfo("America/New_York")),
            session_description=session_description,
        )
        metadata["Subject"].update(
            subject_id=rat,
            species="Rattus norvegicus",
            strain="Long-Evans",
            sex="U",
            description=(
                "Adult Long-Evans rat (Charles River). The rats of the papers were 3 males and 2 females, but the source "
                "does not say which rat had which sex, nor their age or weight."
            ),
        )
        return metadata
