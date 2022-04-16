"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
from scipy.io import loadmat

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.conversion_tools import get_module
from pynwb import NWBFile
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

# TODO
# lots of rich special electrode information, including sync on 104 (sync with what though? video too?)
# behavioral data is only included in a small subset of sessions that did the working memory task
# The main folders have .sts.* files that have timestamps in ms from start of daily session classifying REM vs SWS
#    BUT because we don't have timestamps for the actual start of subsessions, we can't align these since subsessions
#    aren't actually contiguous


class FujisawaMiscInterface(BaseDataInterface):
    """Primary data interface for miscellaneous aspects of the FujisawaS dataset."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(mat_file_path=dict(type="string")))

    def run_conversion(self, nwbfile: NWBFile, metadata: dict):
        mat_file_path = self.source_data["mat_file_path"]
        mat_file = loadmat(mat_file_path)
        trial_info = mat_file["SessionNP"]

        nwbfile.add_trial_column(name="reward_time", description="Time when subject began consuming reward.")
        nwbfile.add_trial_column(name="left_or_right", description="Time when subject began consuming reward.")
        l_r_dict = {1: "Right", 2: "Left"}
        for trial in trial_info:
            nwbfile.add_trial(
                start_time=trial[0], stop_time=trial[1], reward_time=trial[2], left_or_right=l_r_dict[int(trial[3])]
            )

        # Position
        pos_info = mat_file["whlrl"]
        pos_data = [pos_info[:, 0:1], pos_info[:, 2:3]]
        starting_time = 0.0
        rate = 20000 / 512  # from CRCNS info
        conversion = np.nan  # whl are arbitrary units
        pos_obj = Position(name="Position")
        for j in range(2):
            spatial_series_object = SpatialSeries(
                name=f"SpatialSeries{j+1}",
                description="(x,y) coordinates tracking subject movement through the maze.",
                data=H5DataIO(pos_data[j], compression="gzip"),
                reference_frame="unknown",
                conversion=conversion,
                starting_time=starting_time,
                rate=rate,
                resolution=np.nan,
            )
            pos_obj.add_spatial_series(spatial_series_object)
        get_module(
            nwbfile=nwbfile, name="behavior", description="Contains processed behavioral data."
        ).add_data_interface(pos_obj)

        linearized_pos = mat_file["whlrld"][:, 6]
        lin_pos_obj = Position(name="LinearizedPosition")
        lin_spatial_series_object = SpatialSeries(
            name="LinearizedTimeSeries",
            description=(
                "Linearized position, with '1' defined as start position (the position at the time of last nose-poking "
                "in the trial), and d=2 being the end position (position at the tiome just before reward consumption). "
                "d=0 means subject is not performing working memory trials."
            ),
            data=H5DataIO(linearized_pos, compression="gzip"),
            reference_frame="unknown",
            conversion=conversion,
            starting_time=starting_time,
            rate=rate,
            resolution=np.nan,
        )
        lin_pos_obj.add_spatial_series(lin_spatial_series_object)
        get_module(nwbfile=nwbfile, name="behavior").add_data_interface(lin_pos_obj)
