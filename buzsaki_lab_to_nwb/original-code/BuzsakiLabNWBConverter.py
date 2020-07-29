
from NWBConverter import NWBConverter
from BaseDataInterface import NeuroscopeRecordingInterface

class BuzsakiLabNWBConverter(NWBConverter):
    data_interface_classes = {'neuroscope': NeuroscopeRecordingInterface}
    
    