"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from nwb_conversion_tools.baserecordingextractorinterface import BaseRecordingExtractorInterface


class YutaNoRecording(BaseRecordingExtractorInterface):
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
