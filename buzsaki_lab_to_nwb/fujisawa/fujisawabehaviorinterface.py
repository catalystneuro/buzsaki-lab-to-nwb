"""Trials and position of a Fujisawa session (DANDI:000067)."""

from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from pydantic import DirectoryPath
from pynwb import NWBFile, TimeSeries
from pynwb.behavior import Position, SpatialSeries
from pynwb.epoch import TimeIntervals
from scipy.io import loadmat

from .fujisawautils import behavior_files

VIDEO_RATE = 20_000 / 512  # 39.0625 Hz, one frame per 512 samples of the 20 kHz recording
SIDES = {1: "right", 2: "left"}


class FujisawaBehaviorInterface(BaseDataInterface):
    """Trials from the `SessionNP` of the lab's XXX_Behavior.mat file, and the head LED positions from its `whlrld`
    (or from the session's .whl file where there is no behavior file)."""

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        super().__init__(folder_path=folder_path, verbose=verbose)
        self.session_path = Path(folder_path)
        self.session_id = self.session_path.name

    def add_trials(self, nwbfile: NWBFile, session_np: np.ndarray):
        description = (
            "Correct trials of the working memory task (the lab's SessionNP lists only correct trials). A trial starts "
            "at the end of the last nose poke, the paper's trial start, and ends when the rat started consuming the "
            "reward, the paper's trial end."
        )
        nwbfile.trials = TimeIntervals(name="trials", description=description)
        nwbfile.add_trial_column(
            name="nose_poke_start_time",
            description="time the rat started the first nose poke of the trial (s)",
        )
        nwbfile.add_trial_column(
            name="side",
            description="side arm the rat ran to and was rewarded in: 'left' or 'right' (the lab's code: R = 1, L = 2)",
        )
        for first_poke, last_poke_end, reward, side in session_np:
            nwbfile.add_trial(
                start_time=float(last_poke_end),
                stop_time=float(reward),
                nose_poke_start_time=float(first_poke),
                side=SIDES[int(side)],
            )

    def add_position(self, nwbfile: NWBFile, leds: np.ndarray):
        leds = leds.astype(float)
        leds[leds < 0] = np.nan  # -1 marks frames where an LED was not tracked
        position = Position(name="Position")
        for index in range(2):
            position.add_spatial_series(
                SpatialSeries(
                    name=f"led_{index + 1}",
                    description=(
                        f"x and y of head LED {index + 1} in the camera image, in pixels (the scale of the image is not "
                        "documented); NaN where the LED was not tracked"
                    ),
                    data=leds[:, 2 * index : 2 * index + 2],
                    unit="pixels",
                    conversion=1.0,
                    reference_frame="camera image: x to the right and y downward from its top left corner",
                    rate=VIDEO_RATE,
                )
            )
        get_module(nwbfile, "behavior", "behavioral data").add(position)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        files = behavior_files(self.session_path)
        whl_file_path = self.session_path / f"{self.session_id}.whl"
        behavior = loadmat(str(files["all"])) if "all" in files else None
        if behavior is not None and "SessionNP" in behavior:
            self.add_trials(nwbfile, behavior["SessionNP"])
        if behavior is not None and "whlrld" in behavior:
            whlrld = behavior["whlrld"]
            self.add_position(nwbfile, whlrld[:, :4])
            get_module(nwbfile, "behavior").add(
                TimeSeries(
                    name="linearized_position",
                    description=(
                        "the lab's linearized position along the maze, d: 1 at the start position (where the last nose "
                        "poke of a trial ended), 2 at the end position (just before reward consumption), 0 when the rat "
                        "was not in a working memory trial"
                    ),
                    data=whlrld[:, 6],
                    unit="a.u.",
                    rate=VIDEO_RATE,
                )
            )
        elif whl_file_path.is_file():
            self.add_position(nwbfile, np.loadtxt(whl_file_path, ndmin=2)[:, :4])
