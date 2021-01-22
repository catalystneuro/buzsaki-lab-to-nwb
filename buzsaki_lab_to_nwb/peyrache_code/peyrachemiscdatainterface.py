"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
from pathlib import Path
from scipy.io import loadmat
from warnings import warn

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.file import TimeIntervals
from pynwb.behavior import SpatialSeries, Position
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..neuroscope import get_events, check_module


def peyrache_spatial_series(name: str, description: str, data: np.array, pos_sf: float = 1250 / 32):
    """Specific constructor for Peyrache style spatial series."""
    return SpatialSeries(
        name=name,
        description=description,
        data=H5DataIO(data, compression="gzip"),
        conversion=1e-2,  # from cm to m
        reference_frame="Unknown",
        starting_time=0.,
        rate=pos_sf,
        resolution=np.nan
    )


class PeyracheMiscInterface(BaseDataInterface):
    """Primary data interface for miscellaneous aspects of the PeyracheA dataset."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(folder_path=dict(type="string")))

    def run_conversion(self, nwbfile: NWBFile, metadata_dict: dict, stub_test: bool = False):
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.stem

        # Stimuli
        [nwbfile.add_stimulus(x) for x in get_events(session_path)]

        # States
        sleep_state_fpath = session_path / f"{session_id}.SleepState.states.mat"
        # label renaming specific to Peyrache
        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        if sleep_state_fpath.is_file():
            matin = loadmat(sleep_state_fpath)['SleepState']['ints'][0][0]

            table = TimeIntervals(name='states', description="Sleep states of animal.")
            table.add_column(name='label', description="Sleep state.")

            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append(dict(start_time=row[0], stop_time=row[1], label=state_label_names[name]))
            [table.add_row(**row) for row in sorted(data, key=lambda x: x['start_time'])]
            check_module(nwbfile, 'behavior', 'contains behavioral data').add(table)

        # Position
        pos_names = ['RedLED', 'BlueLED']
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
                    data=whl_data[:, idx_from:idx_to]
                )
            )

        # Processed position
        posfile_path = session_path / f"{session_id}.pos"
        try:
            pos_data = np.loadtxt(posfile_path)
            pos_obj = Position(name='SubjectPosition')
            for name, idx_from, idx_to in zip(pos_names, pos_idx_from, pos_idx_to):
                pos_obj.add_spatial_series(
                    peyrache_spatial_series(
                        name=name,
                        description=(
                            "(x,y) coordinates tracking subject movement through the maze."
                            "Values of -1 indicate that LED detection failed."
                        ),
                        data=pos_data[:, idx_from:idx_to]
                    )
                )
            check_module(nwbfile, 'behavior', 'contains processed behavioral data').add(pos_obj)
        except ValueError:  # data issue present in at least Mouse17-170201
            warn(f"Skipping .pos file for session {session_id}!")

        # Epochs
        # epoch_names = list(pos_mat['position']['Epochs'][0][0].dtype.names)
        # epoch_windows = [[float(start), float(stop)]
        #                  for x in pos_mat['position']['Epochs'][0][0][0][0] for start, stop in x]
        # nwbfile.add_epoch_column('label', 'name of epoch')
        # for j, epoch_name in enumerate(epoch_names):
        #     nwbfile.add_epoch(start_time=epoch_windows[j][0], stop_time=epoch_windows[j][1], label=epoch_name)
