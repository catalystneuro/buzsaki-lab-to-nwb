"""Authors: Cody Baker and Ben Dichter."""
from datetime import datetime
from pathlib import Path
from hdf5storage import loadmat  # scipy.io loadmat doesn't support >= v7.3 matlab files

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools.datainterfaces.neuroscopedatainterface import NeuroscopeLFPInterface, \
    NeuroscopeRecordingInterface
from nwb_conversion_tools.datainterfaces.phydatainterface import PhySortingInterface
from nwb_conversion_tools.datainterfaces.cellexplorerdatainterface import CellExplorerSortingInterface

from .petersenmiscdatainterface import PetersenMiscInterface


class PetersenNWBConverter(NWBConverter):
    """Primary conversion class for the PetersenP dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        PhySorting=PhySortingInterface,
        CellExplorer=CellExplorerSortingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        PetersenMisc=PetersenMiscInterface
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects['NeuroscopeLFP'].source_data['file_path'])
        session_path = lfp_file_path.parent
        session_id = lfp_file_path.stem
        if '-' in session_id:
            subject_id, date_text = session_id.split('-')
        session_start = datetime.strptime(session_id[-13:], "%y%m%d_%H%M%S")

        session_info = loadmat(str(session_path / "session.mat"))['session']

        metadata = super().get_metadata()
        metadata['NWBFile'].update(
            experimenter=[y[0][0] for x in session_info['general']['experimenters'] for y in x[0][0]],
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki"
        )
        metadata.update(
            Subject=dict(
                subject_id=session_info['general']['animal'][0][0][0][0],
                species="Rattus norvegicus domestica - Long Evans",
                genotype=session_info['general']['geneticLine'][0][0][0][0],
                sex=session_info['general']['sex'][0][0][0][0],
                age="3-6 months"
            )
        )

        if 'Ecephys' not in metadata:  # If NeuroscopeRecording was not in source_data
            session_path = lfp_file_path.parent
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))

        return metadata
