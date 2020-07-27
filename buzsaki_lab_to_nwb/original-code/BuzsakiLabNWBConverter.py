
import nwb_conversion_tools as nwbct

class BuzsakiLabNWBConverter(nwbct.NWBConverter):
    data_interface_classes = {'neuroscope': NeuroscopeRecordingInterface}
    
    extractor_name = 'NwbRecording'
    has_default_locations = True
    installed = HAVE_NWB  # check at class level if installed or not
    is_writable = True
    mode = 'file'
    installation_mesg = "To use the Nwb extractors, install pynwb: \n\n pip install pynwb\n\n"

    def __init__(self, file_path, electrical_series_name='ElectricalSeries'):
        self.a = 1;