"""Authors: Cody Baker and Ben Dichter."""

import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv import NWBConverter

from .watsonecephysinterface import WatsonEcephysInterface
from .watsonontology import add_ontology_annotations
from .watsonsleepstatesinterface import WatsonSleepStatesInterface
from .watsonsortinginterface import WatsonSortingInterface


class WatsonNWBConverter(NWBConverter):
    """Conversion of the Watson et al. 2016 sessions (DANDI:000041)."""

    # Ecephys must come first: it creates the electrode groups and electrodes that the units refer to
    data_interface_classes = dict(
        Ecephys=WatsonEcephysInterface,
        Sorting=WatsonSortingInterface,
        SleepStates=WatsonSleepStatesInterface,
    )

    def get_metadata(self):
        metadata = super().get_metadata()
        session_id = Path(self.data_interface_objects["Ecephys"].source_data["folder_path"]).name
        subject_id, date_text = session_id.split("_")[:2]
        # The session folders are named by date only (MMDDYY)
        session_date = datetime.strptime(date_text, "%m%d%y")
        metadata["NWBFile"].update(
            session_id=session_id,
            identifier=str(uuid.uuid4()),
            session_start_time=session_date.replace(tzinfo=ZoneInfo("America/New_York")),
        )
        metadata["Subject"]["subject_id"] = subject_id
        return metadata

    def add_to_nwbfile(self, nwbfile, metadata, conversion_options=None):
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        add_ontology_annotations(nwbfile)
