"""Authors: Cody Baker and Ben Dichter."""
from datetime import datetime
from pathlib import Path

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools.datainterfaces.neuroscopedatainterface import NeuroscopeRecordingInterface, \
    NeuroscopeLFPInterface
from nwb_conversion_tools.datainterfaces.cellexplorerdatainterface import CellExplorerSortingInterface

from .girardeaumiscdatainterface import GirardeauMiscInterface


class GirardeauNWBConverter(NWBConverter):
    """Primary conversion class for the GirardeauG dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        CellExplorerSorting=CellExplorerSortingInterface,
        GirardeauMisc=GirardeauMiscInterface
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects['NeuroscopeLFP'].source_data['file_path'])
        session_id = lfp_file_path.stem
        session_start = datetime.strptime(session_id[6:], "%Y%m%d")

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
            "Three silicon probes (2 with 8 shanks, 1 with 4 shanks, 160 recording channels total, NeuroNexus H32 and )"
            "H62, A-style, Buzsaki32 and 64 layout) mounted on individual movable microdrives51 were implanted above "
            "the amygdalae bilaterally (AP −2.5 mm ML ± 3.6 to 5.5 mm from bregma) and in the dorsal hippocampus (left "
            "or right, CA1, AP −3.5 mm, ML ± 2.5 mm). The drives were secured to the skull using dental cement. Skull "
            "screws above the cerebellum were used as ground and reference. The drives and probes were protected by a "
            "cement-covered copper-mesh Faraday cage on which the probe connectors were attached."
        )

        metadata = super().get_metadata()
        metadata['NWBFile'].update(
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki",
            experimenter="Gabrielle Girardeau",
            session_description=paper_descr,
            related_publications=paper_info
        )
        metadata.update(
            Subject=dict(
                species="Rattus norvegicus domestica - Long Evans",
                sex="Male",
                genotype="Wild type",
                weight="300g",
                age="3 months"
            )
        )

        if 'Ecephys' not in metadata:  # If NeuroscopeRecording was not in source_data
            session_path = lfp_file_path.parent
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))
        metadata['Ecephys']['Device'][0].update(description=device_descr)

        return metadata
