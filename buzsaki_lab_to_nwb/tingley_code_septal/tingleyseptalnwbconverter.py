"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
from copy import Error, deepcopy
from collections import Counter
from datetime import datetime

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
    neuronexus_5_12=dict(
        name="Neuronexus probe (5 x 12)",
        description=(
            "A 5 (shanks) x 12 (electrodes) silicon probe from Neuronexus. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with 20 kHz rate."
        ),
    ),
    neuronexus_6_10=dict(
        name="Neuronexus probe (6 x 10)",
        description=(
            "A 6 (shanks) x 10 (electrodes) silicon probe from Neuronexus. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with 20 kHz rate."
        ),
    ),
    neuronexus_8_8=dict(
        name="Neuronexus probe (8 x 8)",
        description=(
            "A 8 (shanks) x 8 (electrodes) silicon probe from Neuronexus. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with 20 kHz rate."
        ),
    ),
    to_be_determined=dict(name="Name to be determined", description=("according to author reference sites a few millimeters dorsal to the rest")),
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

        # Group re-organization
        # original_metadata = deepcopy(metadata)

        extractor = self.data_interface_objects["NeuroscopeLFP"].recording_extractor
        counts = Counter(extractor.get_channel_groups())

        inference_dic = {
            64: "cambridge",
            99: "neuronexus_4_8",  # Can disambiguate between 4x8 and 8x8 with available info.
            12: "neuronexus_5_12",
            8: "neuronexus_8_8",
            10: "neuronexus_6_10",
            4: "to_be_determined",
        }

        inferred_devices = {key: inference_dic[value] for key, value in counts.items()}

        unique_inferred_devices = set(inferred_devices.values())
        metadata["Ecephys"]["Device"] = [DEVICE_INFO[inferred_device] for inferred_device in unique_inferred_devices]
        for group_idx, inferred_device in inferred_devices.items():
            metadata["Ecephys"]["ElectrodeGroup"][group_idx - 1].update(device=DEVICE_INFO[inferred_device]["name"])
        
        return metadata
