"""Authors: Cody Baker and Ben Dichter."""
from dateutil.parser import parse as dateparse
from pathlib import Path

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools.datainterfaces.neuroscopedatainterface import NeuroscopeMultiRecordingTimeInterface, \
    NeuroscopeLFPInterface, NeuroscopeRecordingInterface, NeuroscopeSortingInterface
from nwb_conversion_tools.datainterfaces.cellexplorerdatainterface import CellExplorerSortingInterface

from .peyrachemiscdatainterface import PeyracheMiscInterface


class PeyracheNWBConverter(NWBConverter):
    """Primary conversion class for the GrosmarkAD dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeMultiRecordingTimeInterface,
        NeuroscopeSorting=NeuroscopeSortingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        PeyracheMisc=PeyracheMiscInterface
    )

    def get_metadata(self):
        """Auto-fill all relevant metadata used in run_conversion."""
        lfp_file_path = Path(self.data_interface_objects['NeuroscopeLFP'].source_data['file_path'])
        session_path = lfp_file_path.parent
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
                species="Mus musculus"
            )
        )

        # Unit metadata retrieved from CellExplorer format
        # But still using Neuroscope for waveforms
        spikes_matfile_path = session_path / f"{session_id}.spikes.cellinfo.mat"
        if spikes_matfile_path.is_file():
            sorting_metadata_interface = CellExplorerSortingInterface(spikes_matfile_path=str(spikes_matfile_path))
            sorting_metadata = sorting_metadata_interface.get_metadata()['UnitProperties']
            n_units = len(self.data_interface_objects['NeuroscopeSorting'].sorting_extractor.get_unit_ids())
            if len(sorting_metadata[0]) == n_units:
                print(f"Updating UnitProperties for session {session_id}!")
                metadata['UnitProperties'] = sorting_metadata_interface['UnitProperties']

        if 'Ecephys' not in metadata:  # If NeuroscopeRecording was not in source_data
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))

        return metadata
