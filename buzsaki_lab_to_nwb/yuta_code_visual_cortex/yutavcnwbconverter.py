"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import NWBConverter, NeuroscopeRecordingInterface, NeuroscopeLFPInterface, PhySortingInterface

from .yutavcbehaviorinterface import YutaVCBehaviorInterface
from .yuta_vc_utils import read_matlab_file


class YutaVCNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY visual cortex data set."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        YutaVCBehavior=YutaVCBehaviorInterface,
        PhySorting=PhySortingInterface,
    )

    def __init__(self, source_data: dict):
        super().__init__(source_data=source_data)

        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_path = lfp_file_path.parent
        electrode_chan_map_file_path = session_path / "chanMap.mat"
        chan_map = read_matlab_file(file_path=electrode_chan_map_file_path)
        xcoords = [x[0] for x in chan_map["xcoords"]]
        ycoords = [y[0] for y in chan_map["ycoords"]]
        for channel_id in chan_map["chanMap0ind"]:
            self.data_interface_objects["NeuroscopeLFP"].recording_extractor.set_channel_locations(
                locations=[xcoords[channel_id], ycoords[channel_id]], channel_ids=channel_id
            )
            if "NeuroscopeRecording" in self.data_interface_objects:
                self.data_interface_objects["NeuroscopeRecording"].recording_extractor.set_channel_locations(
                    locations=[xcoords[channel_id], ycoords[channel_id]], channel_ids=channel_id
                )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_id = lfp_file_path.stem

        subject_id, datetime_string = str(lfp_file_path.stem).split("_")
        session_start = datetime.strptime(datetime_string, "%y%m%d")
        session_start = session_start.astimezone(tz=dateutil.tz.gettz("US/Eastern")).isoformat()

        metadata = super().get_metadata()
        metadata["NWBFile"].update(session_start_time=session_start, session_id=session_id)
        metadata.update(Subject=dict(subject_id=subject_id))
        return metadata
