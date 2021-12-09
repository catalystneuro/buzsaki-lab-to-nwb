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
