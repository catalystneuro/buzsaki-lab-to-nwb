"""Tests of the Senzai (DANDI:000003) conversion that need none of the lab's data: every source file is made here."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import h5py
import numpy as np
import pandas as pd
import pytest
from pynwb import NWBFile
from scipy.io import savemat

from buzsaki_lab_to_nwb.yuta_mossy_cell.senzaibehaviorinterface import (
    NO_DIODE,
    TRIAL_COLUMNS,
    SenzaiBehaviorInterface,
    parse_pulse_label,
)
from buzsaki_lab_to_nwb.yuta_mossy_cell.senzaiecephysinterface import (
    SenzaiEcephysInterface,
    auxiliary_channel,
    group_kinds,
)
from buzsaki_lab_to_nwb.yuta_mossy_cell.senzaiutils import (
    NOT_IN_PAPER_NOTE,
    find_frame_offset,
    light_note,
    pixels_to_arena,
    read_exp_sheet,
    read_roi,
    roi_note,
)

LED_RATE = 1250 / 32


def new_nwbfile() -> NWBFile:
    return NWBFile(
        session_description="test",
        identifier="test",
        session_start_time=datetime(2015, 2, 18, tzinfo=ZoneInfo("America/New_York")),
    )


def write_events(folder: Path, session: str, label: str, onsets_ms, text=None):
    lines = [f"{onset:.6f}\t{text or label}" for onset in onsets_ms]
    (folder / f"{session}.{label}.evt").write_text("\n".join(lines) + "\n")


def write_xml(folder: Path, session: str, groups: list, n_channels: int):
    group_text = "".join(
        "<group><channels>" + "".join(f"<channel>{c}</channel>" for c in group) + "</channels></group>"
        for group in groups
    )
    (folder / f"{session}.xml").write_text(
        "<parameters>"
        f"<acquisitionSystem><nChannels>{n_channels}</nChannels><samplingRate>20000</samplingRate></acquisitionSystem>"
        "<fieldPotentials><lfpSamplingRate>1250</lfpSamplingRate></fieldPotentials>"
        "<neuroscope><spikes><nSamples>32</nSamples></spikes></neuroscope>"
        f"<spikeDetection><channelGroups>{group_text}</channelGroups></spikeDetection>"
        "</parameters>"
    )


@pytest.fixture
def session(tmp_path):
    def make(name):
        folder = tmp_path / name
        folder.mkdir()
        return folder

    return make


# ---------------------------------------------------------------- light pulses (findings 3 and 6)


@pytest.mark.parametrize(
    "label, expected",
    [
        ("PulseStim_5V_20ms_LD12", (5.0, 0.02, "12", "PulseStim_5V_20ms_LD12")),
        ("PulseStim_2.5V_1000ms_LD1200", (2.5, 1.0, "1200", "PulseStim_2.5V_1000ms_LD1200")),
        ("PulseStim_10ms", (np.nan, 0.01, NO_DIODE, "PulseStim_10ms")),
        ("PulseStim_1sec", (np.nan, 1.0, NO_DIODE, "PulseStim_1sec")),
        ("PulseStim_1sec_weak", (np.nan, 1.0, NO_DIODE, "PulseStim_1sec_weak")),
        ("PulseStim_1sec2", (np.nan, 1.0, NO_DIODE, "PulseStim_1sec2")),
        ("PulseStim_10ms.ST1", (np.nan, 0.01, NO_DIODE, "PulseStim_10ms.ST1")),
    ],
)
def test_pulse_labels(label, expected):
    voltage, duration, diodes, protocol = parse_pulse_label(label)
    assert (duration, diodes, protocol) == pytest.approx(expected[1:]) or (duration, diodes, protocol) == expected[1:]
    assert (np.isnan(voltage) and np.isnan(expected[0])) or voltage == expected[0]


@pytest.mark.parametrize(
    "label", ["MS_PulseStim", "MS_PulseStim_briefLD", "opto_10ms.ST3", "Ripple", "PeakStim5V", "StimDuringRun_Start"]
)
def test_other_event_files_are_not_pulses(label):
    assert parse_pulse_label(label) is None


def test_duration_only_pulse_files_become_light_pulses(session):
    """The YutaMouse20 and YutaMouse23 pulse files name the duration only; they had no light_pulses table."""
    name = "YutaMouse23-140805"
    folder = session(name)
    ten_ms = 1000.0 * np.arange(1800) + 22452290.4
    one_s = 10000.8 * np.arange(360) + 17041677.6
    write_events(folder, name, "PulseStim_10ms", ten_ms)
    write_events(folder, name, "PulseStim_1sec", one_s)
    write_events(folder, name, "PulseStim_1sec_weak", one_s[-1] + 15000 + 10000.8 * np.arange(180))
    write_events(folder, name, "opto_10ms.ST3", ten_ms, text="opto_10ms start")

    interface = SenzaiBehaviorInterface(folder_path=str(folder))
    nwbfile = new_nwbfile()
    interface.add_light_pulses(nwbfile)
    interface.add_lab_events(nwbfile)

    pulses = nwbfile.intervals["light_pulses"].to_dataframe()
    assert len(pulses) == 1800 + 360 + 180
    assert pulses.protocol.value_counts().to_dict() == {
        "PulseStim_10ms": 1800,
        "PulseStim_1sec": 360,
        "PulseStim_1sec_weak": 180,
    }
    short = pulses[pulses.protocol == "PulseStim_10ms"]
    np.testing.assert_allclose(short.stop_time - short.start_time, 0.01)
    np.testing.assert_allclose(short.start_time.iloc[0], 22452.2904)
    long = pulses[pulses.protocol == "PulseStim_1sec"]
    np.testing.assert_allclose(long.stop_time - long.start_time, 1.0)
    assert pulses.voltage.isna().all() and set(pulses.laser_diodes) == {NO_DIODE}
    assert np.all(np.diff(pulses.start_time) >= 0)
    description = nwbfile.intervals["light_pulses"].description
    assert "name the duration only" in description
    # the Arch SST-Cre mouse: green light, by the paper
    assert "green" in description and "520 nm" in description and "AAV-DIO-Arch" in description
    # the pulse files are no longer also written as instants; the other event files still are
    assert set(nwbfile.processing["events"].data_interfaces) == {"opto_10ms.ST3"}


def test_a_pulse_listed_in_two_duration_only_files_is_kept_once(session):
    """PulseStim_1sec2 of YutaMouse20-140324 is the later half of its PulseStim_1sec."""
    name = "YutaMouse20-140324"
    folder = session(name)
    onsets = 10000.8 * np.arange(720) + 12976700.0
    write_events(folder, name, "PulseStim_1sec", onsets)
    write_events(folder, name, "PulseStim_1sec2", onsets[360:])
    write_events(folder, name, "PulseStim_10ms.ST1", 1000.0 * np.arange(1800) + 18387300.0, text="PulseStim_10ms")

    interface = SenzaiBehaviorInterface(folder_path=str(folder))
    nwbfile = new_nwbfile()
    interface.add_light_pulses(nwbfile)
    table = nwbfile.intervals["light_pulses"]
    pulses = table.to_dataframe()
    assert pulses.protocol.value_counts().to_dict() == {"PulseStim_10ms.ST1": 1800, "PulseStim_1sec": 720}
    assert not pulses.duplicated(["start_time", "stop_time"]).any()
    assert "360 onsets of YutaMouse20-140324.PulseStim_1sec2.evt are also in PulseStim_1sec.evt" in table.description
    assert "blue" in table.description and "450 nm" in table.description  # a ChR2 mouse


def test_named_pulse_files_are_read_as_before(session):
    name = "YutaMouse51-160516"
    folder = session(name)
    write_events(folder, name, "PulseStim_5V_20ms_LD12", [1000.0, 2000.0, 2000.0, 3000.0], text="pulse")
    write_events(folder, name, "PulseStim_5V_500ms_LD1", [1000.0, 9000.0], text="pulse")
    (folder / f"{name}.PulseStim_0V_10001ms_LD0.evt").write_text("")  # an empty file is skipped

    interface = SenzaiBehaviorInterface(folder_path=str(folder))
    nwbfile = new_nwbfile()
    interface.add_light_pulses(nwbfile)
    interface.add_lab_events(nwbfile)
    table = nwbfile.intervals["light_pulses"]
    pulses = table.to_dataframe()
    assert list(pulses.start_time) == [1.0, 1.0, 2.0, 3.0, 9.0]
    assert list(pulses.stop_time) == [1.02, 1.5, 2.02, 3.02, 9.5]
    assert list(pulses.laser_diodes) == ["12", "1", "12", "12", "1"]
    assert set(pulses.voltage) == {5.0}
    assert "PulseStim_5V_20ms_LD12.evt lists 1 onsets twice" in table.description
    assert "name the duration only" not in table.description
    assert "green" in table.description and "DRD2-Cre::Ai35" in table.description
    assert "events" not in nwbfile.processing


def test_light_notes_state_a_colour_only_where_the_paper_does():
    for mouse in ("YutaMouse20", "YutaMouse37", "YutaMouse38", "YutaMouse39", "YutaMouse40"):
        assert "blue" in light_note(mouse) and "450 nm" in light_note(mouse) and "green" not in light_note(mouse)
    for mouse in ("YutaMouse23", "YutaMouse33", "YutaMouse42", "YutaMouse44", "YutaMouse45", "YutaMouse56"):
        assert "account: green" in light_note(mouse) and "520 nm" in light_note(mouse)
        assert "blue" not in light_note(mouse)
    for mouse in ("YutaMouse41", "YutaMouse57"):
        assert light_note(mouse).startswith("Light colour: not stated")
    assert all("do not record the wavelength" in light_note(f"YutaMouse{n}") for n in (20, 23, 33, 41, 45, 57))


# ---------------------------------------------------------------- trials (finding 4)


def test_sens_pass_is_described_as_the_side_arm_sensor():
    description = TRIAL_COLUMNS["sens_pass"]
    assert "side arm" in description and "ch_SsolL" in description and "ch_SsolR" in description
    assert "end of the central arm" not in description


# ---------------------------------------------------------------- positions (finding 7)


def test_arena_coordinates_follow_from_pixels_and_the_roi(tmp_path):
    rng = np.random.default_rng(0)
    pixels = rng.uniform(100, 600, size=(500, 2))
    square = dict(x=316.39, y=146.54, width=238.04, angle=-1.5)
    arena = pixels_to_arena(pixels, square)
    # the ROI corner is the arena's origin, and one width along the turned x axis is (1, 0)
    np.testing.assert_allclose(pixels_to_arena([[316.39, 146.54]], square), [[0, 0]], atol=1e-12)
    angle = np.radians(-1.5)
    along_x = np.array([316.39, 146.54]) + 238.04 * np.array([np.cos(angle), -np.sin(angle)])
    np.testing.assert_allclose(pixels_to_arena([along_x], square), [[1, 0]], atol=1e-12)
    # distances scale by the width: the transform is a rotation and a scaling
    np.testing.assert_allclose(
        np.linalg.norm(arena[1:] - arena[:-1], axis=1) * 238.04, np.linalg.norm(pixels[1:] - pixels[:-1], axis=1)
    )

    circle = dict(xc=425.22, yc=267.35, radius=160.39, angle=0.0)
    np.testing.assert_allclose(pixels_to_arena([[425.22 + 160.39, 267.35]], circle), [[1, 0]], atol=1e-12)

    rectangle = dict(x=20.16, y=52.82, xwidth=617.97, ywidth=350.64, angle=0.0)  # the 'ExtraLarge' arena
    np.testing.assert_allclose(pixels_to_arena([[20.16 + 617.97, 52.82 + 350.64]], rectangle), [[1, 1]], atol=1e-12)
    assert "x = 20.16, y = 52.82, xwidth = 617.97 and ywidth = 350.64 pixels" in roi_note(rectangle, "R.mat")
    assert "/ xwidth, (dx sin(angle) + dy cos(angle)) / ywidth)" in roi_note(rectangle, "R.mat", 0)

    for name, roi in (("open", square), ("maze", circle), ("large", rectangle)):
        savemat(tmp_path / f"{name}.mat", {"ROIparams": roi})
        assert read_roi(tmp_path / f"{name}.mat") == pytest.approx(roi)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_the_frame_offset_between_led_and_arena_positions_is_found(offset):
    rng = np.random.default_rng(1)
    led = rng.uniform(100, 600, size=(2000, 2))
    led[50:60] = np.nan  # frames without a detected LED
    roi = dict(xc=351.5, yc=206.7, radius=172.26, angle=-0.2)
    rows = np.arange(100, 1900)
    times = (rows - offset) / LED_RATE
    arena = pixels_to_arena(led[rows], roi)
    assert find_frame_offset(times, arena, led, roi, LED_RATE) == offset
    assert find_frame_offset(times, arena + 0.01, led, roi, LED_RATE) is None


def test_roi_note_gives_the_numbers_and_states_the_formula_only_when_checked():
    roi = dict(x=316.3917, y=146.5423, width=238.0412, angle=-1.5)
    plain = roi_note(roi, "S__OpenFieldROI_New.mat")
    assert "x = 316.39, y = 146.54 and width = 238.04 pixels, at an angle of -1.50 degrees" in plain
    assert "led0_position" not in plain
    checked = roi_note(roi, "S__OpenFieldROI_New.mat", -1)
    assert checked.startswith(plain) and "one video frame (25.6 ms) earlier" in checked
    maze = roi_note(dict(xc=1.0, yc=2.0, radius=3.0, angle=0.5), "S__EightMazeROI.mat", 0)
    assert "xc = 1.00, yc = 2.00 and radius = 3.00 pixels" in maze and "at the same time" in maze


def test_position_series_carry_the_arena_place_in_the_camera_image(session):
    name = "YutaMouse41-150830"
    folder = session(name)
    rng = np.random.default_rng(2)
    n_frames = 4000
    whl = np.round(np.column_stack([rng.uniform(250, 490, (n_frames, 2)), rng.uniform(250, 490, (n_frames, 2))]), 4)
    whl[10] = -1
    np.savetxt(folder / f"{name}.whl", whl, fmt="%.4f")
    led0 = whl[:, :2].copy()
    led0[10] = np.nan

    def twhl(rows, roi):
        return np.column_stack([(rows + 1) / LED_RATE, pixels_to_arena(led0[rows], roi)])

    maze_roi = dict(xc=351.5, yc=206.7, radius=172.26, angle=-0.2)
    field_roi = dict(x=249.61, y=74.7, width=248.0, angle=0.0)
    maze_rows, field_rows = np.arange(100, 1500), np.arange(2000, 3500)
    norm = twhl(maze_rows, maze_roi)
    linear = np.column_stack([norm[:, 0], np.zeros(len(norm)), np.zeros(len(norm))])
    savemat(folder / f"{name}__EightMazePosition.mat", {"twhl_norm": norm, "twhl_linearized": linear})
    savemat(folder / f"{name}__EightMazeROI.mat", {"ROIparams": maze_roi})
    savemat(folder / f"{name}__OpenFieldPosition_New.mat", {"twhl_norm": twhl(field_rows, field_roi)})
    savemat(folder / f"{name}__OpenFieldROI_New.mat", {"ROIparams": field_roi})
    # an arena without a ROI file gets no note
    savemat(folder / f"{name}__OpenFieldPosition_Old.mat", {"twhl_norm": twhl(np.arange(3500, 3900), field_roi)})

    interface = SenzaiBehaviorInterface(folder_path=str(folder))
    nwbfile = new_nwbfile()
    interface.add_to_nwbfile(nwbfile, metadata={})

    behavior = nwbfile.processing["behavior"]
    maze = behavior["t_maze_position"]["position"]
    assert "xc = 351.50, yc = 206.70 and radius = 172.26 pixels" in maze.description
    assert "one video frame (25.6 ms) earlier" in maze.description
    new = behavior["open_field_position"]["New"]
    assert "x = 249.61, y = 74.70 and width = 248.00 pixels" in new.description
    assert "region of interest" not in behavior["open_field_position"]["Old"].description
    led_description = nwbfile.acquisition["led0_position"].description
    assert "camera pixels" in led_description and "arena coordinates" in led_description
    assert "arena coordinates" not in nwbfile.acquisition["led1_position"].description
    # the file's own numbers reproduce the arena series from the LED pixels
    led = nwbfile.acquisition["led0_position"].data[:]
    rows = np.rint(np.asarray(new.timestamps if new.timestamps is not None else []) * LED_RATE).astype(int)
    if new.timestamps is None:
        rows = np.rint((new.starting_time + np.arange(len(new.data)) / new.rate) * LED_RATE).astype(int)
    np.testing.assert_allclose(pixels_to_arena(led[rows - 1], field_roi), new.data[:], atol=1e-9)


def test_led_series_of_a_home_cage_session_do_not_point_to_arena_positions(session):
    name = "YutaMouse44-151128"
    folder = session(name)
    np.savetxt(folder / f"{name}.whl", np.full((100, 4), 300.0), fmt="%.1f")
    interface = SenzaiBehaviorInterface(folder_path=str(folder))
    nwbfile = new_nwbfile()
    interface.add_to_nwbfile(nwbfile, metadata={})
    assert "arena coordinates" not in nwbfile.acquisition["led0_position"].description


# ---------------------------------------------------------------- probes (finding 5)


def test_group_kinds():
    assert group_kinds([8] * 8, 8) == ["shank"] * 8
    assert group_kinds([8] * 8 + [16, 16], 8) == ["shank"] * 8 + ["linear", "linear"]
    assert group_kinds([10] * 6 + [4, 1], 10) == ["shank"] * 6 + ["other", "other"]


def electrodes_of(folder, name, groups, n_channels, probe):
    write_xml(folder, name, groups, n_channels)
    interface = SenzaiEcephysInterface(folder_path=str(folder), probe=probe)
    nwbfile = new_nwbfile()
    interface.add_electrodes(nwbfile)
    return nwbfile


def test_the_linear_probe_of_yutamouse33_is_a_second_device(session):
    name = "YutaMouse33-150218"
    groups = [list(range(8 * i, 8 * i + 8)) for i in range(8)] + [list(range(64, 80)), list(range(80, 96))]
    nwbfile = electrodes_of(session(name), name, groups, 112, "Buzsaki64")
    assert set(nwbfile.devices) == {"probe", "linear_probe"}
    assert "8 shanks 200 um apart, each with 8 staggered" in nwbfile.devices["probe"].description
    assert "10 shanks" not in nwbfile.devices["probe"].description
    assert "channel groups 9 and 10" in nwbfile.devices["linear_probe"].description
    for index in range(1, 9):
        assert nwbfile.electrode_groups[f"shank{index}"].device.name == "probe"
    for index, half in ((9, "top"), (10, "bottom")):
        group = nwbfile.electrode_groups[f"shank{index}"]
        assert group.device.name == "linear_probe"
        assert f"'{half}'" in group.description and "not a shank" in group.description
    electrodes = nwbfile.electrodes.to_dataframe()
    assert len(electrodes) == 96
    assert list(electrodes.group_name.value_counts().loc[["shank9", "shank10"]]) == [16, 16]


def test_channel_groups_that_are_not_shanks_are_not_counted_as_shanks(session):
    name = "YutaMouse20-140321"
    groups = [list(range(4 + 10 * i, 14 + 10 * i)) for i in range(6)] + [[0, 1, 2, 3], [64]]
    nwbfile = electrodes_of(session(name), name, groups, 65, "Buzsaki64sp")
    assert set(nwbfile.devices) == {"probe"}
    description = nwbfile.devices["probe"].description
    assert "6 shanks 200 um apart, each with 10 staggered" in description
    assert "group 7 with 4 channels, group 8 with 1 channel" in description
    assert (
        "4 channels of the recording that are not on a 10-site shank" in nwbfile.electrode_groups["shank7"].description
    )
    assert "1 channel of the recording that is not on a 10-site shank" in nwbfile.electrode_groups["shank8"].description
    assert nwbfile.electrode_groups["shank1"].description.startswith("shank1 of the probe")


def test_an_eight_shank_probe_is_described_as_before_apart_from_the_site_count(session):
    name = "YutaMouse41-150830"
    nwbfile = electrodes_of(session(name), name, [list(range(8 * i, 8 * i + 8)) for i in range(8)], 80, "Buzsaki64")
    assert nwbfile.devices["probe"].description == (
        "NeuroNexus silicon probe (Buzsaki64): 8 shanks 200 um apart, each with 8 staggered recording sites 20 um "
        "apart vertically"
    )


TWO_PROBE_GROUPS = [
    [33, 38, 32, 39, 35, 36, 34, 37],
    [41, 46, 40, 47, 43, 44, 42, 45],
    [16, 25, 17, 24, 18, 22, 20, 21],
    [26, 19, 28, 23, 29, 27, 30, 31],
    [13, 4, 9, 2, 5, 3, 1, 0],
    [7, 14, 6, 15, 8, 12, 11, 10],
    [48, 55, 49, 54, 50, 53, 51, 52],
    [56, 63, 57, 62, 58, 61, 59, 60],
    list(range(64, 80)),
    list(range(80, 96)),
]


def write_earlier_file(path: Path, lfp: np.ndarray, amp_channel=None, auxiliary=None, lfp_name="LFP"):
    """A stand-in for a session's file in the earlier DANDI version, with the groups the conversion reads."""
    with h5py.File(path, "w") as file:
        series = file.create_group(f"processing/ecephys/LFP/{lfp_name}")
        series.create_dataset("data", data=lfp)
        series.create_dataset("starting_time", data=0.0).attrs["rate"] = 1250.0
        electrodes = file.create_group("general/extracellular_ephys/electrodes")
        electrodes.create_dataset("id", data=np.arange(lfp.shape[1]))
        if amp_channel is not None:
            electrodes.create_dataset("amp_channel", data=np.asarray(amp_channel))
        for name, data in (auxiliary or {}).items():
            group = file.create_group(f"acquisition/{name}")
            group.create_dataset("data", data=data)
            group.create_dataset("starting_time", data=0.0).attrs["rate"] = 1250.0


def convert_ecephys(folder, name, groups, n_channels, probe, earlier_file):
    write_xml(folder, name, groups, n_channels)
    interface = SenzaiEcephysInterface(folder_path=str(folder), published_nwb_file_path=str(earlier_file), probe=probe)
    nwbfile = new_nwbfile()
    interface.add_to_nwbfile(nwbfile, metadata={})
    return nwbfile


def lfp_channels(nwbfile):
    """The channel_id of each LFP column, through the series' electrodes."""
    series = nwbfile.processing["ecephys"]["LFP"]["lfp"]
    channel_ids = np.asarray(nwbfile.electrodes["channel_id"][:])
    return series, [int(channel) for channel in channel_ids[np.asarray(series.electrodes.data[:])]]


def test_auxiliary_inputs_are_the_last_16_channels_of_a_recording():
    assert auxiliary_channel(70, 80) == 70
    assert auxiliary_channel(70, 112) == 102  # sensor 1 of the YutaMouse33 sheet
    assert auxiliary_channel(79, 112) == 111
    assert auxiliary_channel(65, 65) is None  # the YutaMouse20 and YutaMouse23 recordings have no inputs


def test_the_2019_earlier_file_gets_lfp_and_inputs_from_the_eeg_file(session):
    """YutaMouse33-150218: the earlier file holds 64 LFP columns in the order of the shanks, and its auxiliary
    series are not the inputs; the share's .eeg file has all 112 channels."""
    name = "YutaMouse33-150218"
    folder = session(name)
    rng = np.random.default_rng(3)
    eeg = rng.integers(-2000, 2000, size=(3000, 112), dtype=np.int16)
    eeg.tofile(folder / f"{name}.eeg")
    order = [channel for group in TWO_PROBE_GROUPS[:8] for channel in group]
    earlier = folder / "earlier.nwb"
    write_earlier_file(
        earlier, eeg[:, order], amp_channel=order, auxiliary={"ch_SsolR": np.zeros(112, np.int16)}, lfp_name="lfp"
    )
    nwbfile = convert_ecephys(folder, name, TWO_PROBE_GROUPS, 112, "Buzsaki64", earlier)

    series, channels = lfp_channels(nwbfile)
    assert channels == list(range(96))
    np.testing.assert_array_equal(series.data.data[:], eeg[:, :96])
    assert f"{name}.eeg" in series.description and "64 of the 96 probe channels" in series.description
    right_sensor = nwbfile.acquisition["ch_SsolR"]
    np.testing.assert_array_equal(right_sensor.data[:], eeg[:, 102])
    assert "channel 102" in right_sensor.description and f"{name}.eeg" in right_sensor.description
    np.testing.assert_array_equal(nwbfile.acquisition["ch_wait"].data[:], eeg[:, 111])
    assert len([key for key in nwbfile.acquisition if key.startswith("ch_")]) == 10


def test_without_the_eeg_file_the_2019_columns_keep_their_own_channels(session):
    name = "YutaMouse33-150218"
    folder = session(name)
    rng = np.random.default_rng(4)
    signal = rng.integers(-2000, 2000, size=(500, 112), dtype=np.int16)
    order = [channel for group in TWO_PROBE_GROUPS[:8] for channel in group]
    earlier = folder / "earlier.nwb"
    write_earlier_file(earlier, signal[:, order], amp_channel=order, auxiliary={"ch_SsolR": np.zeros(112, np.int16)})
    nwbfile = convert_ecephys(folder, name, TWO_PROBE_GROUPS, 112, "Buzsaki64", earlier)
    series, channels = lfp_channels(nwbfile)
    assert channels == order  # column 0 is channel 33, not channel 0
    assert "not the order of the channel numbers" in series.description
    # the earlier file's "auxiliary" series of a 112-channel recording are probe channels: they are left out
    assert not [key for key in nwbfile.acquisition if key.startswith("ch_")]


def test_an_eeg_file_that_is_not_the_earlier_lfp_is_not_used(session):
    name = "YutaMouse33-150219"
    folder = session(name)
    rng = np.random.default_rng(5)
    signal = rng.integers(-2000, 2000, size=(500, 112), dtype=np.int16)
    other = signal.copy()
    other[100, 3] += 1
    other.tofile(folder / f"{name}.eeg")
    earlier = folder / "earlier.nwb"
    write_earlier_file(earlier, signal[:, :96], auxiliary={"ch_arm": signal[:, 78]})
    nwbfile = convert_ecephys(folder, name, TWO_PROBE_GROUPS, 112, "Buzsaki64", earlier)
    series, channels = lfp_channels(nwbfile)
    assert channels == list(range(96)) and ".eeg" not in series.description
    assert "ch_arm" not in nwbfile.acquisition


def test_a_2021_file_of_a_two_probe_recording_takes_the_inputs_from_the_eeg_file(session):
    """The other YutaMouse33 files: 96 LFP columns in channel order, and series named as inputs that are copies of
    probe channels 65 to 79."""
    name = "YutaMouse33-150223"
    folder = session(name)
    rng = np.random.default_rng(6)
    eeg = rng.integers(-2000, 2000, size=(800, 112), dtype=np.int16)
    eeg.tofile(folder / f"{name}.eeg")
    earlier = folder / "earlier.nwb"
    write_earlier_file(earlier, eeg[:, :96], auxiliary={"ch_arm": eeg[:, 78], "ch_SsolL": eeg[:, 73]})
    nwbfile = convert_ecephys(folder, name, TWO_PROBE_GROUPS, 112, "Buzsaki64", earlier)
    series, channels = lfp_channels(nwbfile)
    assert channels == list(range(96)) and ".eeg" not in series.description  # the LFP is still the earlier file's
    np.testing.assert_array_equal(nwbfile.acquisition["ch_arm"].data[:], eeg[:, 110])
    np.testing.assert_array_equal(nwbfile.acquisition["ch_SsolL"].data[:], eeg[:, 105])
    assert "channel 105" in nwbfile.acquisition["ch_SsolL"].description
    assert "150223session9,10" in nwbfile.acquisition["ch_SsolL"].description


def test_an_80_channel_recording_keeps_the_earlier_file_series(session):
    name = "YutaMouse41-150830"
    folder = session(name)
    rng = np.random.default_rng(7)
    signal = rng.integers(-2000, 2000, size=(600, 80), dtype=np.int16)
    earlier = folder / "earlier.nwb"
    write_earlier_file(earlier, signal[:, :64], auxiliary={"ch_SsolR": signal[:, 70], "ch_wait": signal[:, 79]})
    groups = [list(range(8 * i, 8 * i + 8)) for i in range(8)]
    nwbfile = convert_ecephys(folder, name, groups, 80, "Buzsaki64", earlier)
    series, channels = lfp_channels(nwbfile)
    assert channels == list(range(64))
    assert series.description == "LFP of the probe channels: the wide-band signal down-sampled to 1250 Hz by the lab"
    np.testing.assert_array_equal(nwbfile.acquisition["ch_SsolR"].data[:], signal[:, 70])
    assert nwbfile.acquisition["ch_SsolR"].description == (
        "auxiliary input on channel 70 of the recording system: sensor 1, right side arm, in the system's raw int16 "
        "steps (the scaling of these inputs is not documented)"
    )
    assert set(key for key in nwbfile.acquisition if key.startswith("ch_")) == {"ch_SsolR", "ch_wait"}


# ---------------------------------------------------------------- subjects (findings 1 and 6)


def write_exp_sheet(path: Path, details_first: bool, genotype="SST-Cre"):
    details = pd.DataFrame(
        [["YM#39", None], ["mouseID", "SST15-4"], ["genotype", genotype], ["DOB", pd.Timestamp("2014-08-20")]]
    )
    log = pd.DataFrame([[None, "implanted", None], [None, pd.Timestamp("2015-07-27"), "H"]])
    sheets = [("Sheet1", details), ("Sheet2", log)] if details_first else [("Sheet2", log), ("Sheet1", details)]
    with pd.ExcelWriter(path) as writer:
        for sheet_name, frame in sheets:
            frame.to_excel(writer, sheet_name=sheet_name, header=False, index=False)


@pytest.mark.parametrize("details_first", [True, False])
def test_exp_sheet_details_are_read_from_whichever_tab_holds_them(tmp_path, details_first):
    """YM39's workbook has the recording log as its first tab, so its genotype and date of birth were not read."""
    path = tmp_path / "YM39 exp_sheet.xlsx"
    write_exp_sheet(path, details_first)
    sheet = read_exp_sheet(path)
    assert sheet["genotype"] == "SST-Cre"
    assert pd.Timestamp(sheet["DOB"]) == pd.Timestamp("2014-08-20")


def test_note_for_the_mouse_that_is_not_in_the_paper():
    assert "not in the paper's Table S1" in NOT_IN_PAPER_NOTE and "counts" in NOT_IN_PAPER_NOTE
