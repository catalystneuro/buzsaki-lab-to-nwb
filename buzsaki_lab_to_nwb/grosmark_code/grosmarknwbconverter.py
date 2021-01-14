"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from datetime import datetime
import warnings

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools import NeuroscopeLFPInterface, CellExplorerSortingInterface

from .grosmarkbehaviordatainterface import GrosmarkBehaviorInterface


class GrosmarkNWBConverter(NWBConverter):
    """Primary conversion class for the GrosmarkAD dataset."""

    data_interface_classes = dict(
        CellExplorerSorting=CellExplorerSortingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        GrosmarkBehavior=GrosmarkBehaviorInterface
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects['NeuroscopeLFP'].source_data['file_path'])
        session_id = lfp_file_path.stem
        session_start = datetime.strptime(session_id[-8:], "%m%d%Y")

        metadata = super().get_metadata()
        metadata['NWBFile'].update(
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki"
        )
        metadata.update(
            Subject=dict(
                species="Mus musculus"
            )
        )

        return metadata
