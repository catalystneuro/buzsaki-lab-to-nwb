"""Authors: Cody Baker and Ben Dichter."""
from datetime import datetime
from pathlib import Path

import numpy as np
from hdf5storage import loadmat  # scipy.io loadmat doesn't support >= v7.3 matlab files

from nwb_conversion_tools import (
    NWBConverter,
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    PhySortingInterface,
    CellExplorerSortingInterface,
)

from .petersenmiscdatainterface import PetersenMiscInterface


class PetersenNWBConverter(NWBConverter):
    """Primary conversion class for the PetersenP dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        PhySorting=PhySortingInterface,
        CellExplorer=CellExplorerSortingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        PetersenMisc=PetersenMiscInterface,
    )

    # def __init__(self, source_data: dict):
    #     super().__init__(source_data=source_data)
    #     lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
    #     session_path = lfp_file_path.parent
    #     session_info = loadmat(str(session_path / "session.mat"))["session"]
    #     theta_ref = np.array(
    #         [False] * self.data_interface_objects["NeuroscopeLFP"].recording_extractor.get_num_channels()
    #     )
    #     theta_ref[int(session_info["channelTags"]["Theta"][0][0][0][0][0][0]) - 1] = True  # -1 from Matlab indexing
    #     for j, channel_id in enumerate(
    #         self.data_interface_objects["NeuroscopeLFP"].recording_extractor.get_channel_ids()
    #     ):
    #         self.data_interface_objects["NeuroscopeLFP"].recording_extractor.set_channel_property(
    #             channel_id=channel_id, property_name="theta_reference", value=theta_ref[j]
    #         )

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
        session_start = datetime.strptime(datetime_string, "%y%m%d_%H%M%S").astimezone().strftime("%Y-%m-%dT%H:%M:%S")

        session_info = loadmat(str(session_path / "session.mat"))["session"]
        paper_descr = (
            "Petersen et al. demonstrate that cooling of the medial septum slows theta oscillation and increases "
            "choice errors without affecting spatial features of pyramidal neurons. Cooling affects distance-time, "
            "but not distance-theta phase, compression. The findings reveal that cell assemblies are organized by "
            "theta phase and not by external (clock) time."
        )
        paper_info = (
            "Cooling of Medial Septum Reveals Theta Phase Lag Coordination of Hippocampal Cell Assemblies."
            "Petersen P, Buzsaki G, Neuron. 2020"
        )

        device_descr = (
            "The five rats were implanted with multi-shank 64-site silicon probes bilaterally in the CA1 pyramidal "
            "layer of the dorsal hippocampus."
        )

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            experimenter=[y[0][0] for x in session_info["general"]["experimenters"] for y in x[0][0]],
            session_start_time=session_start,
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
            metadata.update(Ecephys=NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))

        metadata["Ecephys"]["Device"][0].update(description=device_descr)
        # metadata["Ecephys"]["Electrodes"].append(
        #     dict(name="theta_reference", description="If the channel used as theta reference.")
        # )
        return metadata
