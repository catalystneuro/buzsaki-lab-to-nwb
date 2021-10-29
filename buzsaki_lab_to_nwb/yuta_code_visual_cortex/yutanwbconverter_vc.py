from nwb_conversion_tools import NWBConverter, NeuroscopeRecordingInterface, NeuroscopeLFPInterface


class YutaVCNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY visual cortex data set."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface, NeuroscopeLFP=NeuroscopeLFPInterface
    )
