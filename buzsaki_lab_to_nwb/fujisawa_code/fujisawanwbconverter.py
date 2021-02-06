"""Authors: Cody Baker and Ben Dichter."""
from dateutil.parser import parse as dateparse
from pathlib import Path

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools.datainterfaces.neuroscopedatainterface import NeuroscopeMultiRecordingTimeInterface, \
    NeuroscopeLFPInterface, NeuroscopeRecordingInterface
from nwb_conversion_tools.datainterfaces.cellexplorerdatainterface import CellExplorerSortingInterface

from .fujisawamiscdatainterface import FujisawaMiscInterface


class FujisawaNWBConverter(NWBConverter):
    """Primary conversion class for the FujisawaS dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeMultiRecordingTimeInterface,
        CellExplorerSorting=CellExplorerSortingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        PetersenMisc=PetersenMiscInterface
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects['NeuroscopeLFP'].source_data['file_path'])
        session_id = lfp_file_path.stem
        if '-' in session_id:
            subject_id, date_text = session_id.split('-')
        session_start = dateparse(date_text[-4:] + date_text[:-4])

        metadata = super().get_metadata()
        metadata['NWBFile'].update(
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki"
        )
        metadata.update(
            Subject=dict(
                species="Rattus norvegicus domestica - Long Evans",
                sex="Male",
                age="3-6 months",
                genotype="Wild type"
            )
        )

        if 'Ecephys' not in metadata:  # If NeuroscopeRecording was not in source_data
            session_path = lfp_file_path.parent
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))

        return metadata
