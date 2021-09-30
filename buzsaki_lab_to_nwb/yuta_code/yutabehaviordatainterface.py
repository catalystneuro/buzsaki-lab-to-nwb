"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
import numpy as np
from scipy.io import loadmat

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.file import TimeIntervals
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..neuroscope import get_events, find_discontinuities, check_module


class YutaBehaviorInterface(BaseDataInterface):
    """Interface for converting processed behavioral data for the Yuta experiments (visual cortex)."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(folder_path=dict(type="string")))

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        session_path = Path(self.source_data["folder_path"])
        task_types = [
            dict(name="OpenFieldPosition_ExtraLarge"),
            dict(name="OpenFieldPosition_New_Curtain", conversion=0.46),
            dict(name="OpenFieldPosition_New", conversion=0.46),
            dict(name="OpenFieldPosition_Old_Curtain", conversion=0.46),
            dict(name="OpenFieldPosition_Old", conversion=0.46),
            dict(name="OpenFieldPosition_Oldlast", conversion=0.46),
            dict(name="EightMazePosition", conversion=0.65 / 2),
        ]

        subject_path = session_path.parent
        session_id = session_path.stem

        [nwbfile.add_stimulus(x) for x in get_events(session_path)]

        sleep_state_fpath = session_path / f"{session_id}--StatePeriod.mat"

        exist_pos_data = any(
            [
                (session_path / "{session_id}__{task_type['name']}.mat").is_file()
                for task_type in task_types
            ]
        )
        if exist_pos_data:
            nwbfile.add_epoch_column("label", "Name of epoch.")

        # Epoch intervals
        for task_type in task_types:
            label = task_type["name"]

            file = session_path / f"{session_id}__{label}.mat"
            if file.is_file():
                pos_obj = Position(name=f"{label}_position")

                matin = loadmat(file)
                tt = matin["twhl_norm"][:, 0]
                exp_times = find_discontinuities(tt)

                if "conversion" in task_type:
                    conversion = task_type["conversion"]
                else:
                    conversion = np.nan

                for pos_type in ("twhl_norm", "twhl_linearized"):
                    if pos_type in matin:
                        pos_data_norm = matin[pos_type][:, 1:]

                        spatial_series_object = SpatialSeries(
                            name=f"{label}_{pos_type}_spatial_series",
                            data=H5DataIO(pos_data_norm, compression="gzip"),
                            reference_frame="unknown",
                            conversion=conversion,
                            resolution=np.nan,
                            timestamps=H5DataIO(tt, compression="gzip"),
                        )
                        pos_obj.add_spatial_series(spatial_series_object)

                check_module(
                    nwbfile, "behavior", "Contains processed behavioral data."
                ).add_data_interface(pos_obj)
                for i, window in enumerate(exp_times):
                    nwbfile.add_epoch(
                        start_time=window[0],
                        stop_time=window[1],
                        tags=f"{label}_{str(i)}",
                    )

        # Trial intervals
        trialdata_path = session_path / f"{session_id}__EightMazeRun.mat"
        if trialdata_path.is_file():
            trials_data = loadmat(trialdata_path)["EightMazeRun"]

            trialdatainfo_path = subject_path / "EightMazeRunInfo.mat"
            trialdatainfo = [
                x[0] for x in loadmat(trialdatainfo_path)["EightMazeRunInfo"][0]
            ]

            features = trialdatainfo[:7]
            features[:2] = (
                "start_time",
                "stop_time",
            )
            [
                nwbfile.add_trial_column(x, "description")
                for x in features[4:] + ["condition"]
            ]

            for trial_data in trials_data:
                if trial_data[3]:
                    cond = "run_left"
                else:
                    cond = "run_right"
                nwbfile.add_trial(
                    start_time=trial_data[0],
                    stop_time=trial_data[1],
                    condition=cond,
                    error_run=trial_data[4],
                    stim_run=trial_data[5],
                    both_visit=trial_data[6],
                )

        # SLeep states
        if sleep_state_fpath.is_file():
            matin = loadmat(sleep_state_fpath)["StatePeriod"]
            table = TimeIntervals(name="states", description="sleep states of animal")
            table.add_column(name="label", description="sleep state")
            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append(dict(start_time=row[0], stop_time=row[1], label=name))
            [
                table.add_row(**row)
                for row in sorted(data, key=lambda x: x["start_time"])
            ]
            check_module(
                nwbfile, "behavior", "Contains behavioral data."
            ).add_data_interface(table)
