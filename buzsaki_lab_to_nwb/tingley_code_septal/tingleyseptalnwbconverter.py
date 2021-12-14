"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
from datetime import datetime
from copy import deepcopy

from nwb_conversion_tools import (
    NWBConverter,
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeSortingInterface,
    CellExplorerSortingInterface,
)

from .tingleyseptalbehaviorinterface import TingleySeptalBehaviorInterface


DEVICE_INFO = dict(
    cambridge=dict(
        name="Cambridge prob (1 x 64)",
        description=(
            "Silicon probe from Cambridge Neurotech. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with20 kHz rate."
        ),
    ),
    neuronexus_4_8=dict(
        name="Neuronexus probe (4 x 8)",
        description=(
            "A 4 (shanks) x 8 (electrodes) silicon probe from Neuronexus. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with 20 kHz rate."
        ),
    ),
    # TODO: add other types
)


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
        split = session_id.split("_")

        if "DT" in split[0]:
            date = split[5]
        else:
            date = split[0]

        if date == "20170229":
            date = "20170228"  # 2017 is not a leap year (?!)

        if split[-1] == "merge":
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

        original_metadata = deepcopy(metadata)
        # look at original_metadata["Ecephys"]["ElectrodeGroups"]
        # for each group, count # electrodes
        # count # of consecutive jumps between # of electrodes
        # inferred_devices = dict(1="this device", ... 8="other device")
        inferred_devices = dict()
        unique_inferred_devices = set(inferred_devices.values())
        metadata["Ecephys"]["Device"] = [DEVICE_INFO for inferred_device in unique_inferred_devices]
        for group_idx, inferred_device in inferred_devices.items():
            metadata["Ecephys"]["ElectrodeGroup"][group_idx].update(device="map_to_correct_device")
        return metadata
