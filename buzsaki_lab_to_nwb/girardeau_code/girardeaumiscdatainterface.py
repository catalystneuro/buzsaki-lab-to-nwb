"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from scipy.io import loadmat
import pandas as pd

from nwb_conversion_tools.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.file import TimeIntervals

from ..neuroscope import get_events, check_module, add_position_data


# TODO
# Add mpg movies as acquisition image series
#    mpg's are broken up by epoch
#    .mpg's cannot be uploaded to DANDI, but hard to support converison of frames to np.array, so skipping for now
# LapType mat files seem to have some info on the air puffs and mouse track runs, but it's hard to decipher and
#     not much documentation on it

class GirardeauMiscInterface(BaseDataInterface):
    """Primary data interface for miscellaneous aspects of the GirardeauG dataset."""

    @classmethod
    def get_source_schema(cls):
        return dict(properties=dict(folder_path=dict(type="string")))

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        stub_test: bool = False,
     ):
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.name

        # Stimuli
        [
            nwbfile.add_stimulus(x)
            for x in get_events(session_path=session_path, suffixes=[".lrw.evt", ".puf.evt", ".rip.evt", ".rrw.evt"])
        ]

        # Epochs
        df = pd.read_csv(
            session_path / f"{session_id}.cat.evt",
            sep=" ",
            names=("time", "begin_or_end", "of", "epoch_name")
        )
        epoch_starts = []
        for j in range(int(len(df)/2)):
            epoch_starts.append(df['time'][2 * j])
            nwbfile.add_epoch(
                start_time=epoch_starts[j],
                stop_time=df['time'][2 * j + 1],
                tags=[df['epoch_name'][2 * j][18:]]
            )

        # Trials
        trialdata_path = session_path / f"{session_id}-TrackRunTimes.mat"
        if trialdata_path.is_file():
            trials_data = loadmat(trialdata_path)['trackruntimes']
            for trial_data in trials_data:
                nwbfile.add_trial(start_time=trial_data[0], stop_time=trial_data[1])

        # .whl position
        whl_files = []
        for whl_file in whl_files:
            add_position_data(
                nwbfile=nwbfile,
                session_path=session_path,
                whl_file_path=whl_file,
                starting_time=epoch_starts[j]
            )

        # States
        sleep_state_fpath = session_path / f"{session_id}.SleepState.states.mat"
        # label renaming
        state_label_names = dict(WAKEstate="Awake", NREMstate="Non-REM", REMstate="REM")
        if sleep_state_fpath.is_file():
            matin = loadmat(sleep_state_fpath)['SleepState']['ints'][0][0]

            table = TimeIntervals(name="states", description="Sleep states of animal.")
            table.add_column(name="label", description="Sleep state.")

            data = []
            for name in matin.dtype.names:
                for row in matin[name][0][0]:
                    data.append(dict(start_time=row[0], stop_time=row[1], label=state_label_names[name]))
            [table.add_row(**row) for row in sorted(data, key=lambda x: x['start_time'])]
            check_module(nwbfile, "behavior", "Contains behavioral data.").add(table)
