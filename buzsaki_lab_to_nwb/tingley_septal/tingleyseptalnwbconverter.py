"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
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
from .tingleyseptal_utils import read_matlab_file


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
    old_neuronexus_probe=dict(
        name="Neuronexus probe (4 x 1)",
        description=(
            "according to author thse are reference sites a few millimeters dorsal from the rest"
            "recorded from an older neuronexus probe"
        ),
    ),
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

    def __init__(self, source_data: dict):
        super().__init__(source_data=source_data)

        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_path = lfp_file_path.parent
        session_id = session_path.stem

        # Add region
        session_info_matfile_path = session_path / f"{session_id}.sessionInfo.mat"

        if session_info_matfile_path.is_file():
            session_info_matfile = read_matlab_file(session_info_matfile_path)["sessionInfo"]
            channel_region_list = session_info_matfile.get("region", None)
            recording_extractor = self.data_interface_objects["NeuroscopeLFP"].recording_extractor
            recording_extractor.set_property(key="brain_area", values=channel_region_list)

            if "NeuroscopeRecording" in self.data_interface_objects:
                recording_extractor = self.data_interface_objects["NeuroscopeRecording"].recording_extractor
                recording_extractor.set_property(key="brain_area", values=channel_region_list)

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])

        session_path = lfp_file_path.parent
        subject = str(session_path.parent.stem)
        session_id = session_path.stem
        subject_id = session_path.parent.name

        # See the names in the valid session for this logic
        split = session_id.split("_")

        if split[0] == "DT1":
            date = split[2]
        elif split[0] == "DT2":
            date = split[5]
        else:
            date = split[0]

        if date == "20170229":
            date = "20170228"  # 2017 is not a leap year (?!)

        if split[-1] == "merge" or split[0] == "DT1":
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

        # Group mapping
        extractor = self.data_interface_objects["NeuroscopeLFP"].recording_extractor
        channel_groups = extractor.get_channel_groups()
        counts = Counter(channel_groups)  # group_id : number_of_channels relationship

        inference_dic = {
            64: "cambridge",
            8: "neuronexus_4_8",
            12: "neuronexus_5_12",
            88: "neuronexus_8_8",  # Can disambiguate between 4x8 and 8x8 with available info.
            10: "neuronexus_6_10",
            4: "old_neuronexus_probe",
            3: "neuronexus_4_8",
        }

        if subject == "DT9":  # This subject can be disambiguated by the number of channels per group
            inferred_devices = {i: inference_dic[8] for i in range(1, 5)}
            inferred_devices.update({i: inference_dic[88] for i in range(5, 5 + 8)})
        else:
            inferred_devices = {key: inference_dic[value] for key, value in counts.items()}

        unique_inferred_devices = set(inferred_devices.values())
        metadata["Ecephys"]["Device"] = [DEVICE_INFO[inferred_device] for inferred_device in unique_inferred_devices]
        for group_idx, inferred_device in inferred_devices.items():
            metadata["Ecephys"]["ElectrodeGroup"][group_idx - 1].update(device=DEVICE_INFO[inferred_device]["name"])

        # Add region to groups
        session_info_matfile_path = session_path / f"{session_id}.sessionInfo.mat"
        if session_info_matfile_path.is_file():
            session_info_matfile = read_matlab_file(session_info_matfile_path)["sessionInfo"]
            channel_region_list = session_info_matfile.get("region", None)
            if channel_region_list:
                channel_group_to_region = {
                    group: region for (group, region) in zip(channel_groups, channel_region_list)
                }
                for group_idx, region in channel_group_to_region.items():
                    metadata["Ecephys"]["ElectrodeGroup"][group_idx - 1].update(location=region)

        return metadata
