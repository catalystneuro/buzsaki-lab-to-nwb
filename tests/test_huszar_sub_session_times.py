"""The Huszar position interface stops when a sub-session's number and its timestamps point to different epochs.

The inputs are small and made up. The epoch times are those of e16_3m2_211211 (DANDI:000552), the session whose
Behavior.mat gives sub-session 3 (the linear track) the times of sub-session 2 (the open field).
"""

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile
from scipy.io import savemat

from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics.behaviorinterface import (
    HuszarPositionInterface,
)
from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics.huszarutils import (
    check_sub_session_times,
    epochs_at,
)

SESSION_ID = "e16_3m2_211211"
EPOCHS = [
    dict(name=f"{SESSION_ID}_111236", startTime=0.0, stopTime=5269.92),
    dict(name=f"{SESSION_ID}_124133", startTime=5269.92, stopTime=6532.992),
    dict(name=f"{SESSION_ID}_130348", startTime=6532.992, stopTime=9559.136),
    dict(name=f"{SESSION_ID}_140259", startTime=9559.136, stopTime=12001.92),
    dict(name=f"{SESSION_ID}_144454", startTime=12001.92, stopTime=15123.616),
    dict(name=f"{SESSION_ID}_154701", startTime=15123.616, stopTime=16771.168),
    dict(name=f"{SESSION_ID}_161105", startTime=16771.168, stopTime=20484.032),
]
# The tracked sub-sessions, in the lab's order: figure-8 maze, open field, linear track
FOLDERS = [f"{SESSION_ID}_124133", f"{SESSION_ID}_140259", f"{SESSION_ID}_154701"]
MAZE_INFO = ["tmaze_familiar", "openField_thomas", "linear_manu"]
# First and last sample of each sub-session; sub-session 3 as it should be, and 5564.48 s too early as in the source
SPANS = {1: (5294.141, 6524.019), 2: (9571.230, 11995.848), 3: (15139.818, 16767.467)}
MISPLACED_SPAN = (9575.338, 11202.987)


def times(span, count=50):
    return np.linspace(span[0], span[1], count)


def test_epochs_at():
    assert epochs_at(6000.0, EPOCHS) == [f"{SESSION_ID}_124133"]
    assert epochs_at(30000.0, EPOCHS) == []


@pytest.mark.parametrize("number", [1, 2, 3])
def test_consistent_sub_sessions_pass(number):
    assert check_sub_session_times(number, times(SPANS[number]), FOLDERS, EPOCHS) == [FOLDERS[number - 1]]


def test_times_of_another_sub_session_raise():
    with pytest.raises(ValueError, match="sub-session 3 .* 9575.338 to 11202.987 s.*140259.*sub-session 2"):
        check_sub_session_times(3, times(MISPLACED_SPAN), FOLDERS, EPOCHS, source="Behavior.mat")


def test_times_of_another_sub_session_raise_without_own_folder():
    """A source copy without Tracking.Behavior.mat lists only the folders of the maze blocks of Behavior.mat."""
    with pytest.raises(ValueError, match="not in an epoch of its own"):
        check_sub_session_times(3, times(MISPLACED_SPAN), FOLDERS[:2], EPOCHS)


def test_times_outside_the_tracked_sub_sessions_raise():
    """Times in an epoch without tracking (a home-cage period), while the sub-session's own folder is an epoch."""
    with pytest.raises(ValueError, match="111236.*not in the epoch of its own recording folder"):
        check_sub_session_times(1, times((100.0, 1300.0)), FOLDERS, EPOCHS)


def test_number_below_one_raises():
    with pytest.raises(ValueError, match="start at 1"):
        check_sub_session_times(0, times(SPANS[1]), FOLDERS, EPOCHS)


def test_nothing_to_compare():
    """No epoch holds the times, or there are no times: the check has nothing to compare and does not raise."""
    assert check_sub_session_times(1, times((30000.0, 31000.0)), FOLDERS, EPOCHS) == []
    assert check_sub_session_times(1, np.array([]), FOLDERS, EPOCHS) == []
    assert check_sub_session_times(1, times(SPANS[1]), [""], []) == []


def cell(values):
    array = np.empty(len(values), dtype=object)
    array[:] = values
    return array


def write_session(folder, behavior_spans):
    """A session folder with session.mat, maze_info.mat, Tracking.Behavior.mat (3 sub-sessions) and Behavior.mat
    (the maze blocks, numbered 1 and 3, with the given first and last sample times)."""
    folder.mkdir()
    savemat(folder / f"{SESSION_ID}.session.mat", dict(session=dict(epochs=cell(EPOCHS))))
    savemat(folder / "maze_info.mat", dict(maze_info=cell(MAZE_INFO)))

    count = 50
    tracking_times = np.concatenate([times(SPANS[number], count) for number in (1, 2, 3)])
    tracking = dict(
        folders=cell(FOLDERS),
        timestamps=tracking_times,
        position=dict(x=np.linspace(1.0, 30.0, 3 * count), y=np.linspace(2.0, 20.0, 3 * count)),
        events=dict(
            subSessions=np.array(
                [[epoch["startTime"], epoch["stopTime"]] for epoch in EPOCHS if epoch["name"] in FOLDERS]
            ),
            subSessionsMask=np.repeat([1, 2, 3], count),
        ),
    )
    savemat(folder / f"{SESSION_ID}.Tracking.Behavior.mat", dict(tracking=tracking))

    behavior_times = np.concatenate([times(span, count) for span in behavior_spans.values()])
    behavior = dict(
        timestamps=behavior_times,
        position=dict(
            x=np.linspace(0.0, 90.0, 2 * count),
            y=np.linspace(0.0, 90.0, 2 * count),
            lin=np.linspace(0.0, 200.0, 2 * count),
        ),
        masks=dict(recording=np.repeat(list(behavior_spans), count).astype("uint8")),
        events=dict(recordings=np.array([span[0] for span in behavior_spans.values()])),
        description=cell(["alternation", "linearMaze"]),
    )
    savemat(folder / f"{SESSION_ID}.Behavior.mat", dict(behavior=behavior))
    return folder


def test_position_interface_writes_consistent_session(tmp_path):
    folder = write_session(tmp_path / SESSION_ID, {1: SPANS[1], 3: SPANS[3]})
    nwbfile = mock_NWBFile()
    HuszarPositionInterface(folder_path=str(folder)).add_to_nwbfile(nwbfile=nwbfile, metadata=dict())

    series = nwbfile.processing["behavior"]["SubjectPosition"].spatial_series
    assert sorted(series) == [
        "SpatialSeries1_tmaze_familiar",
        "SpatialSeries2_openField_thomas",
        "SpatialSeries3_linear_manu",
    ]
    for number, name in enumerate(sorted(series), start=1):
        timestamps = series[name].timestamps[:]
        assert check_sub_session_times(number, timestamps, FOLDERS, EPOCHS) == [FOLDERS[number - 1]]
        assert FOLDERS[number - 1] in series[name].description


def test_position_interface_stops_on_misplaced_sub_session(tmp_path):
    """Behavior.mat numbers its second maze block 3 and gives it times in the epoch of sub-session 2."""
    folder = write_session(tmp_path / SESSION_ID, {1: SPANS[1], 3: MISPLACED_SPAN})
    nwbfile = mock_NWBFile()
    with pytest.raises(ValueError, match="sub-session 3 in Behavior.mat"):
        HuszarPositionInterface(folder_path=str(folder)).add_to_nwbfile(nwbfile=nwbfile, metadata=dict())
    assert "behavior" not in nwbfile.processing
