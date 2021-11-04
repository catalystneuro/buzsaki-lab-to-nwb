"""Authors: Heberto Mayorquin and Cody Baker."""
from pathlib import Path
from datetime import datetime
import dateutil

from nwb_conversion_tools import NWBConverter, NeuroscopeRecordingInterface, NeuroscopeLFPInterface, PhySortingInterface

from buzsaki_lab_to_nwb.yuta_code_visual_cortex.yutavcbehaviorinterface import YutaVCBehaviorInterface


class YutaVCNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY visual cortex data set."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        YutaVCBehavior=YutaVCBehaviorInterface,
        PhySorting=PhySortingInterface,
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_id = lfp_file_path.stem

        subject_id, datetime_string = str(lfp_file_path.stem).split("_")
        tz = dateutil.tz.gettz("US/Eastern")
        session_start = datetime.strptime(datetime_string, "%y%m%d")
        session_start = session_start.astimezone(tz=tz).isoformat()

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            experimenter=["Yuta Senzai"],
            session_start_time=session_start,
            session_id=session_id,
        )
        metadata.update(Subject=dict(subject_id=subject_id))
        return metadata
