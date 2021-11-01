from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import NWBConverter, NeuroscopeRecordingInterface, NeuroscopeLFPInterface

from buzsaki_lab_to_nwb.yuta_code_visual_cortex.yutavcbehaviorinterface import YutaVCBehaviorInterface


class YutaVCNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY visual cortex data set."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        YutaVCBehavior=YutaVCBehaviorInterface,
    )

    def get_metadata(self):

        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_id = lfp_file_path.stem

        subject_id, datetime_string = str(lfp_file_path.stem).split("_")
        session_start = datetime.strptime(datetime_string, "%y%m%d").astimezone().strftime("%Y-%m-%d")

        paper_descr = (
            "The relationship between mesoscopic local field potentials (LFPs) and single-neuron firing in the"
            "multi-layered neocortex is poorly understood. Simultaneous recordings from all layers in the primary "
            "visual cortex (V1) of the behaving mouse revealed functionally defined layers in V1. The depth of maximum"
            "spike power and sink-source distributions of LFPs provided consistent laminar landmarks across animals. "
            "Coherence of gamma oscillations (30–100 Hz) and spike-LFP coupling identified six physiological layers and"
            "further sublayers. Firing rates, burstiness, and other electrophysiological features of neurons displayed"
            "unique layer and brain state dependence. Spike transmission strength from layer 2/3 cells to layer 5"
            "pyramidal cells and interneurons was stronger during waking compared with non-REM sleep but stronger"
            "during non-REM sleep among deep-layer excitatory neurons. A subset of deep-layer neurons was active"
            "exclusively in the DOWN state of non-REM sleep. These results bridge mesoscopic LFPs and single-neuron"
            "interactions with laminar structure in V1."
        )
        paper_info = (
            "Senzai, Y., Fernandez-Ruiz, A., & Buzsáki, G. (2019). Layer-specific physiological features and"
            "interlaminar interactions in the primary visual cortex of the mouse. Neuron, 101(3), 500-513."
        )

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            experimenter=["Yuta Senzai"],
            session_start_time=session_start,
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki",
            session_description=paper_descr,
            related_publications=paper_info,
        )

        # Subject
        metadata.update(
            Subject=dict(
                subject_id=subject_id,
                species="Mus musculus",
                sex="Male",
                weight="28-35g",
                age="3-8 months",
            )
        )

        device_descr = (
            "Electrophysiological data were acquired using an Intan RHD2000 system (Intan Technologies LLC) "
            "digitized with 20 kHz rate."
        )

        # If NeuroscopeRecording/LFP was not in source_data
        if "Ecephys" not in metadata:
            session_path = lfp_file_path.parent
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(Ecephys=NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))

        metadata["Ecephys"]["Device"][0].update(description=device_descr)

        return metadata
