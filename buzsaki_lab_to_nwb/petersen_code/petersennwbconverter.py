"""Authors: Cody Baker and Ben Dichter."""
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from hdf5storage import loadmat  # scipy.io loadmat doesn't support >= v7.3 matlab files

from nwb_conversion_tools import (
    NWBConverter,
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    PhySortingInterface,
    CellExplorerSortingInterface,
)
from nwb_conversion_tools.utils.json_schema import FilePathType, OptionalFilePathType
from nwb_conversion_tools.datainterfaces.ecephys.neuroscope.neuroscopedatainterface import (
    get_xml_file_path, get_shank_channels
)

from .petersenmiscdatainterface import PetersenMiscInterface


class PetersenNeuroscopeRecordingInterface(NeuroscopeRecordingInterface):
    """Temporary RecordingInterface until next nwbct version."""

    def __init__(
        self, file_path: FilePathType, gain: Optional[float] = None, xml_file_path: OptionalFilePathType = None
    ):
        super(NeuroscopeRecordingInterface, self).__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)
        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=self.source_data["file_path"])
        self.subset_channels = get_shank_channels(xml_file_path=xml_file_path, sort=True)
        shank_channels = get_shank_channels(xml_file_path)
        group_electrode_numbers = [x for channels in shank_channels for x, _ in enumerate(channels)]
        group_names = [f"shank{n + 1}" for n, channels in enumerate(shank_channels) for _ in channels]
        for channel_id, group_electrode_number, group_name in zip(
            self.recording_extractor.get_channel_ids(), group_electrode_numbers, group_names
        ):
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="shank_electrode_number", value=group_electrode_number
            )
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="group_name", value=group_name
            )


class PetersenNeuroscopeLFPInterface(NeuroscopeLFPInterface):
    """Temporary RecordingInterface until next nwbct version."""

    def __init__(
        self, file_path: FilePathType, gain: Optional[float] = None, xml_file_path: OptionalFilePathType = None
    ):
        super(NeuroscopeLFPInterface, self).__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)
        self.subset_channels = get_shank_channels(
            xml_file_path=get_xml_file_path(data_file_path=self.source_data["file_path"]), sort=True
        )


class PetersenNWBConverter(NWBConverter):
    """Primary conversion class for the PetersenP dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=PetersenNeuroscopeRecordingInterface,
        PhySorting=PhySortingInterface,
        CellExplorer=CellExplorerSortingInterface,
        NeuroscopeLFP=PetersenNeuroscopeLFPInterface,
        PetersenMisc=PetersenMiscInterface,
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_path = lfp_file_path.parent
        session_id = lfp_file_path.stem
        if "-" in session_id:
            subject_id, date_text = session_id.split("-")
        if "concat" not in session_id:
            datetime_string = session_id[-13:]
        else:
            datetime_string = session_id[-20:-7]
        session_start = datetime.strptime(datetime_string, "%y%m%d_%H%M%S")

        session_info = loadmat(str(session_path / "session.mat"))["session"]
        paper_descr = (
            "Petersen et al. demonstrate that cooling of the medial septum slows theta oscillation and increases "
            "choice errors without affecting spatial features of pyramidal neurons. Cooling affects distance-time, "
            "but not distance-theta phase, compression. The findings reveal that cell assemblies are organized by "
            "theta phase and not by external (clock) time."
        )
        paper_info = [
            "Cooling of Medial Septum Reveals Theta Phase Lag Coordination of Hippocampal Cell Assemblies."
            "Petersen P, Buzsaki G, Neuron. 2020"
        ]

        device_descr = (
            "The five rats were implanted with multi-shank 64-site silicon probes bilaterally in the CA1 pyramidal "
            "layer of the dorsal hippocampus."
        )

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            experimenter=[
                y[0][0]
                for x in session_info["general"]["experimenters"]
                for y in x[0][0]
            ],
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki",
            session_description=paper_descr,
            related_publications=paper_info,
        )
        metadata.update(
            Subject=dict(
                subject_id=session_id[6:10],
                species="Rattus norvegicus domestica - Long Evans",
                genotype="Wild type",
                sex="Male",
                age="3-6 months",
            )
        )

        # If NeuroscopeRecording/LFP was not in source_data
        if "Ecephys" not in metadata:
            session_path = lfp_file_path.parent
            xml_file_path = str(session_path / f"{session_id}.xml")
            metadata.update(
                Ecephys=NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)
            )

        metadata["Ecephys"]["Device"][0].update(description=device_descr)
        theta_ref = np.array(
            [False] * self.data_interface_objects["NeuroscopeLFP"].recording_extractor.get_num_channels()
        )
        theta_ref[int(session_info["channelTags"]["Theta"][0][0][0][0][0][0]) - 1] = 1  # -1 from Matlab indexing
        metadata["Ecephys"]["Electrodes"].append(
            dict(
                name="theta_reference",
                description="Channel used as theta reference.",
                data=list(theta_ref),
            )
        )
        return metadata
