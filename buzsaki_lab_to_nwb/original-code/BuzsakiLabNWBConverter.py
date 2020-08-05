
from nwb_conversion_tools import NWBConverter, NeuroscopeDataInterface

class BuzsakiLabNWBConverter(NWBConverter):
    data_interface_classes = {'NeuroscopeRecording': NeuroscopeDataInterface.NeuroscopeRecordingInterface,
                              'NeuroscopeSorting': NeuroscopeDataInterface.NeuroscopeSortingInterface}
    
    