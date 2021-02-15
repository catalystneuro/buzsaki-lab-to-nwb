"""Authors: Cody Baker and Ben Dichter."""
from dateutil.parser import parse as dateparse
from pathlib import Path

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools.datainterfaces.neuroscopedatainterface import NeuroscopeMultiRecordingTimeInterface, \
    NeuroscopeLFPInterface, NeuroscopeRecordingInterface
from nwb_conversion_tools.datainterfaces.cellexplorerdatainterface import CellExplorerSortingInterface

from .girardeaumiscdatainterface import GirardeauMiscInterface


class GirardeauNWBConverter(NWBConverter):
    """Primary conversion class for the GirardeauG dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeMultiRecordingTimeInterface,
        CellExplorerSorting=CellExplorerSortingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        GirardeauMisc=GirardeauMiscInterface
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects['NeuroscopeLFP'].source_data['file_path'])
        session_id = lfp_file_path.stem
        if '-' in session_id:
            subject_id, date_text = session_id.split('-')
        session_start = dateparse(date_text[-4:] + date_text[:-4])

        experimenter = "Gabrielle Girardeau"
        paper_descr = (
            "The consolidation of context-dependent emotional memory requires communication between the hippocampus"
            "and the basolateral amygdala (BLA), but the mechanisms of this process are unknown. We recorded neuronal"
            "ensembles in the hippocampus and BLA while rats learned the location of an aversive air puff on a linear"
            "track, as well as during sleep before and after training. We found coordinated reactivations between the"
            "hippocampus and the BLA during non-REM sleep following training. These reactivations peaked during"
            "hippocampal sharp wave-ripples (SPW-Rs) and involved a subgroup of BLA cells positively modulated during"
            "hippocampal SPW-Rs. Notably, reactivation was stronger for the hippocampus-BLA correlation patterns"
            "representing the run direction that involved the air puff than for the 'safe' direction. These findings"
            "suggest that consolidation of contextual emotional memory occurs during ripple-reactivation of"
            "hippocampus-amygdala circuits."
        )
        paper_info = [
            "Reactivations of emotional memory in the hippocampus-amygdala system during sleep."
            "Girardeau G, Inema I, Buzsáki G. Nature Neuroscience, 2017."
        ]
        device_descr = (
            "8-shank Neuronexus silicon probes."
        )

        metadata = super().get_metadata()
        metadata['NWBFile'].update(
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki",
            experimenter=experimenter,
            session_description=paper_descr,
            related_publications=paper_info
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
        metadata['Ecephys']['Device'][0].update(description=device_descr)

        return metadata
