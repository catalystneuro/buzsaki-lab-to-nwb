"""Authors: Cody Baker."""
import dateutil
from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import (
    NWBConverter,
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
)

from .tingleymetabolicaccelerometerinterface import TingleyMetabolicAccelerometerInterface
from .tingleymetabolicglucoseinterface import TingleyMetabolicGlucoseInterface
from .tingleymetabolicripplesinterface import TingleyMetabolicRipplesInterface
from ..common_interfaces.sleepstatesinterface import SleepStatesInterface


DEVICE_INFO = dict(
    cambridge=dict(
        name="Cambridge probe (1 x 64)",
        description=(
            "Silicon probe from Cambridge Neurotech. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with20 kHz rate."
        ),
    ),
    neuronexus_4_8=dict(
        name="Neuronexus probe (1 x 32)",
        description=(
            "Silicon probe from Cambridge Neurotech. Electrophysiological data were "
            "acquired using an Intan RHD2000 system (Intan Technologies LLC) digitized with20 kHz rate."
        ),
    ),
)


class TingleyMetabolicConverter(NWBConverter):
    """Primary conversion class for the Tingley Metabolic data project."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        Accelerometer=TingleyMetabolicAccelerometerInterface,
        Glucose=TingleyMetabolicGlucoseInterface,
        SleepStates=SleepStatesInterface,
        Ripples=TingleyMetabolicRipplesInterface,
    )

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])

        session_path = lfp_file_path.parent
        session_id = session_path.stem

        session_id_split = session_id.split("_")[:-2]
        subject_id = session_id_split[0]

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            session_id=session_id,
            session_start_time=str(self.data_interface_objects["Glucose"].session_start_time),
        )
        metadata.update(Subject=dict(subject_id=subject_id))
        if "NeuroscopeRecording" in self.data_interface_objects:
            metadata["Ecephys"].update(ElectricalSeries_raw=dict(name="ElectricalSeriesRaw"))
        return metadata
