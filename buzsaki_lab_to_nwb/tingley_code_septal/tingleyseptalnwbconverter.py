"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import NWBConverter, NeuroscopeRecordingInterface, NeuroscopeLFPInterface, PhySortingInterface

class TingleySeptalNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY visual cortex data set."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        PhySorting=PhySortingInterface,
    )
