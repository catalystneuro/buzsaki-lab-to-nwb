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

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            experimenter=["Yuta Senzai"],
            session_start_time=session_start,
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki",
        )

        # Subject
        metadata.update(
            Subject=dict(
                subject_id=subject_id,
                species="Mus musculus",
                sex="M",
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
