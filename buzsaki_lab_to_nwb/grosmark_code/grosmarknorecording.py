"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.baserecordingextractorinterface import BaseRecordingExtractorInterface
import spikeextractors as se


class GrosmarkNoRecording(BaseRecordingExtractorInterface):
    RX = se.NumpyRecordingExtractor

    def convert_data(self, nwbfile, metadata, stub_test=False):
        se.NwbRecordingExtractor.add_devices(
            recording=self.recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata
        )

        se.NwbRecordingExtractor.add_electrode_groups(
            recording=self.recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata
        )

        se.NwbRecordingExtractor.add_electrodes(
            recording=self.recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata
        )
