"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import (
    NWBConverter,
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeSortingInterface,
    CellExplorerSortingInterface,
)

from .tingleyseptalbehaviorinterface import TingleySeptalBehaviorInterface


class TingleySeptalNWBConverter(NWBConverter):
    """Primary conversion class for the Tingley Septal data project"""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        NeuroscopeSorting=NeuroscopeSortingInterface,
        CellExplorerSorting=CellExplorerSortingInterface,
        TingleySeptalBehavior=TingleySeptalBehaviorInterface,
    )

    
    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])

        session_path = lfp_file_path.parent
        session_id = session_path.stem
        subject_id = session_path.parent.name
        split = session_id.split('_')
        
        if 'DT' in split[0]:  
            date = split[5]
        else:
            date = split[0]

        if date == '20170229':
            date = '20170228'  # 2017 is not a leap year (?!)

        if split[-1] == 'merge':
            datetime_string = date
            session_start = datetime.strptime(datetime_string, "%Y%m%d")
        else:
            time = split[-1]
            datetime_string = date + time
            session_start = datetime.strptime(datetime_string, "%Y%m%d%H%M%S")

        session_start = session_start.replace(tzinfo=dateutil.tz.gettz("US/Eastern")).isoformat()
        metadata = super().get_metadata()
 
        metadata["NWBFile"].update(session_start_time=session_start, session_id=session_id)
        metadata.update(Subject=dict(subject_id=subject_id))
        return metadata
