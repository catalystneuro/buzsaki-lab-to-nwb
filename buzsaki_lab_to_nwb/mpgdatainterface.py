"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
import numpy as np

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile, H5DataIO
from pynwb.image import ImageSeries


try:
    import cv2
except ImportError:
    CV_INSTALL = False
    assert CV_INSTALL, "Please install opencv to use this extractor (pip install opencv-python)!"


class MPGInterface(BaseDataInterface):
    """Data interface for writing movies as ImageSeries."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(file_paths=dict(type="array")))

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        stub_test: bool = False,
    ):
        if stub_test:
            count_max = 10
        else:
            count_max = np.inf

        (major_ver, minor_ver, subminor_ver) = (cv2.__version__).split(".")
        file_paths = self.source_data["file_paths"]
        for file in file_paths:
            cap = cv2.VideoCapture(file)
            if int(major_ver) < 3:
                fps = cap.get(cv2.cv.CV_CAP_PROP_FPS)
            else:
                fps = cap.get(cv2.CAP_PROP_FPS)

            success, frame = cap.read()
            mov = [frame]
            count = 1
            while success and count < count_max:
                success, frame = cap.read()
                mov.append(frame)
                count += 1
            mov = np.array(mov)
            cap.release()

            video = ImageSeries(
                name=f"Video: {Path(file).name}",
                description="Video recorded by camera.",
                data=H5DataIO(mov, compression="gzip"),
                rate=fps,
            )
            nwbfile.add_acquisition(video)
