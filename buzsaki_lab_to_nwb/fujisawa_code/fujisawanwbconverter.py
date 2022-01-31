"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools.datainterfaces.neuroscopedatainterface import NeuroscopeRecordingInterface, \
    NeuroscopeLFPInterface, NeuroscopeSortingInterface

from .fujisawamiscdatainterface import FujisawaMiscInterface


class FujisawaNWBConverter(NWBConverter):
    """Primary conversion class for the FujisawaS dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        NeuroscopeSorting=NeuroscopeSortingInterface,
        Misc=FujisawaMiscInterface
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_id = lfp_file_path.parent.name
        subject_id, _ = lfp_file_path.stem.split('.')
        datetime_string = "2008" + lfp_file_path.parent.parent.name[2:6]
        session_start = datetime.strptime(datetime_string, "%Y%m%d")

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki"
        )
        metadata.update(
            Subject=dict(
                subject_id=lfp_file_path.parent.parent.parent.name,
                species="Rattus norvegicus domestica",
                sex="Male",
                age="3-5 months"
            )
        )

        if "Ecephys" not in metadata:  # If NeuroscopeRecording was not in source_data
            session_path = lfp_file_path.parent
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))

        return metadata
