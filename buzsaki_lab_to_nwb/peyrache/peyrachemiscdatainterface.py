"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
from pathlib import Path
from scipy.io import loadmat
from warnings import warn
import pandas as pd

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.file import TimeIntervals
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO
from spikeextractors import NeuroscopeRecordingExtractor

from ..neuroscope import get_events, check_module


def peyrache_spatial_series(name: str, description: str, data: np.array, conversion: float, pos_sf: float = 1250 / 32):
    """Specific constructor for Peyrache style spatial series."""
    return SpatialSeries(
        name=name,
        description=description,
        data=H5DataIO(data, compression="gzip"),
        conversion=conversion,
        reference_frame="Unknown",
        starting_time=0.0,
        rate=pos_sf,
        resolution=np.nan,
    )


class PeyracheMiscInterface(BaseDataInterface):
    """Primary data interface for miscellaneous aspects of the PeyracheA dataset."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(folder_path=dict(type="string")))

    def run_conversion(self, nwbfile: NWBFile, metadata_dict: dict, stub_test: bool = False):
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem

        # Stimuli
        [nwbfile.add_stimulus(x) for x in get_events(session_path)]

        # States
        sleep_state_fpath = session_path / f"{session_id}.SleepState.states.mat"
        # label renaming specific to Peyrache
        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        if sleep_state_fpath.is_file():
            matin = loadmat(sleep_state_fpath)["SleepState"]["ints"][0][0]

            table = TimeIntervals(name="states", description="Sleep states of animal.")
            table.add_column(name="label", description="Sleep state.")

            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append(dict(start_time=row[0], stop_time=row[1], label=state_label_names[name]))
            [table.add_row(**row) for row in sorted(data, key=lambda x: x["start_time"])]
            check_module(nwbfile, "behavior", "Contains behavioral data.").add(table)

        # Position
        pos_names = ["RedLED", "BlueLED"]
        pos_idx_from = [0, 2]
        pos_idx_to = [2, 4]

        # Raw position
        whlfile_path = session_path / f"{session_id}.whl"
        whl_data = np.loadtxt(whlfile_path)
        for name, idx_from, idx_to in zip(pos_names, pos_idx_from, pos_idx_to):
            nwbfile.add_acquisition(
                peyrache_spatial_series(
                    name=name,
                    description="Raw sensor data. Values of -1 indicate that LED detection failed.",
                    data=whl_data[:, idx_from:idx_to],
                    conversion=np.nan,  # whl file is in arbitrary grid units
                )
            )

        # Processed position
        posfile_path = session_path / f"{session_id}.pos"
        if posfile_path.is_file():  # at least Mouse32-140820 was missing a .pos file
            try:
                pos_data = np.loadtxt(posfile_path)
                pos_obj = Position(name="SubjectPosition")
                for name, idx_from, idx_to in zip(pos_names, pos_idx_from, pos_idx_to):
                    pos_obj.add_spatial_series(
                        peyrache_spatial_series(
                            name=name,
                            description=(
                                "(x,y) coordinates tracking subject movement through the maze."
                                "Values of -1 indicate that LED detection failed."
                            ),
                            data=pos_data[:, idx_from:idx_to],
                            conversion=1e-2,  # from cm to m
                        )
                    )
                check_module(nwbfile, "behavior", "Contains behavioral data.").add(pos_obj)
            except ValueError:  # data issue present in at least Mouse17-170201
                warn(f"Skipping .pos file for session {session_id}!")

        # Epochs - only available for sessions with raw data
        epoch_file = session_path / "raw" / f"{session_id}-raw-info" / f"{session_id}-behaviors.txt"
        if epoch_file.is_file():
            epoch_data = pd.read_csv(epoch_file, header=1)[f"{session_id}:"]
            epoch_dat_inds = []
            epoch_names = []
            for epochs in epoch_data:
                inds, name = epochs.split(": ")
                epoch_dat_inds.append(inds.split(" "))
                epoch_names.append(name)

            epoch_windows = [0]
            for epoch in epoch_dat_inds:
                exp_end_times = []
                for dat_ind in epoch:
                    recording_file = session_path / "raw" / f"{session_id}{dat_ind}.dat"
                    info_extractor = NeuroscopeRecordingExtractor(recording_file)
                    dat_end_time = info_extractor.get_num_frames() / info_extractor.get_sampling_frequency()  # seconds
                    exp_end_times.extend([dat_end_time])
                epoch_windows.extend([epoch_windows[-1] + sum(exp_end_times)] * 2)
            epoch_windows = np.array(epoch_windows[:-1]).reshape(-1, 2)

            for j, epoch_name in enumerate(epoch_names):
                nwbfile.add_epoch(start_time=epoch_windows[j][0], stop_time=epoch_windows[j][1], tags=[epoch_name])
