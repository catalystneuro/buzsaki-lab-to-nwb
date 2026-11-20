"""Tests of the Tingley metabolic conversion (DANDI:000233) on small made-up inputs.

The modules are loaded by file path, with stand-ins for the two names they take from nwb_conversion_tools: importing
the `tingley_metabolic` package needs nwb_conversion_tools and spikeextractors, which are retired and do not install
next to current pynwb.
"""

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile
from scipy.io import savemat

FOLDER = Path(__file__).parent.parent / "buzsaki_lab_to_nwb" / "tingley_metabolic"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(f"tingley_metabolic_{name}", FOLDER / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conversion_tools(monkeypatch):
    """Stand-ins for nwb_conversion_tools.basedatainterface.BaseDataInterface and ...nwb_helpers.get_module."""

    class BaseDataInterface:
        def __init__(self, **source_data):
            self.source_data = source_data

    def get_module(nwbfile, name, description=None):
        if name in nwbfile.processing:
            return nwbfile.processing[name]
        return nwbfile.create_processing_module(name=name, description=description)

    package = types.ModuleType("nwb_conversion_tools")
    basedatainterface = types.ModuleType("nwb_conversion_tools.basedatainterface")
    basedatainterface.BaseDataInterface = BaseDataInterface
    tools = types.ModuleType("nwb_conversion_tools.tools")
    nwb_helpers = types.ModuleType("nwb_conversion_tools.tools.nwb_helpers")
    nwb_helpers.get_module = get_module
    for module in (package, basedatainterface, tools, nwb_helpers):
        monkeypatch.setitem(sys.modules, module.__name__, module)


def write_ripples_file(file_path: Path, starts: np.ndarray, peaks: np.ndarray, stops: np.ndarray, samples: int = 7):
    """A ripples.events.mat with the fields the interface reads, in seconds from the start of the ecephys recording."""
    count = len(starts)
    column = np.arange(count, dtype=float).reshape(-1, 1)
    maps = np.arange(count * samples, dtype=float).reshape(count, samples)
    ripples = dict(
        timestamps=np.column_stack((starts, stops)),
        peaks=peaks.reshape(-1, 1),
        peakNormedPower=column + 5.0,
        data=dict(duration=(stops - starts).reshape(-1, 1), peakFrequency=column + 150.0, peakAmplitude=column + 1.0),
        maps=dict(ripples=maps, frequency=maps + 1.0, phase=maps + 2.0, amplitude=maps + 3.0),
    )
    savemat(file_path, dict(ripples=ripples))


def test_ripple_peaks_are_on_the_clock_of_start_and_stop(tmp_path, conversion_tools):
    starts = np.array([10.0, 20.5, 31.25, 47.0])
    peaks = starts + 0.03
    stops = starts + 0.08
    file_path = tmp_path / "CGM1_210125_143404.ripples.events.mat"
    write_ripples_file(file_path, starts=starts, peaks=peaks, stops=stops)
    ecephys_start_time = 86400.0 + 123.5  # the ecephys recording starts this long after the session start

    module = load_module("tingleymetabolicripplesinterface")
    interface = module.TingleyMetabolicRipplesInterface(mat_file_paths=[file_path])
    nwbfile = mock_NWBFile()
    interface.run_conversion(nwbfile=nwbfile, metadata=dict(), ecephys_start_time=ecephys_start_time)

    table = nwbfile.processing["ecephys"]["Ripples"]
    start_time, stop_time, peak = (np.asarray(table[name].data[:]) for name in ("start_time", "stop_time", "peak"))
    np.testing.assert_allclose(start_time, ecephys_start_time + starts)
    np.testing.assert_allclose(stop_time, ecephys_start_time + stops)
    np.testing.assert_allclose(peak, ecephys_start_time + peaks)
    assert np.all((start_time <= peak) & (peak <= stop_time))
    np.testing.assert_allclose(np.asarray(table["duration"].data[:]), stops - starts)
    assert "session start time" in table["peak"].description
    assert "start_time and stop_time" in table["peak"].description


def test_session_datetime_key_ignores_the_separator():
    utils = load_module("tingley_metabolic_utils")
    assert utils.get_session_datetime_key("CGM1_210125_143404") == "210125_143404"
    assert utils.get_session_datetime_key("CGM1-210125-143404") == "210125_143404"
    assert utils.get_session_datetime_key("CGM1_792um_181201_110104") == "181201_110104"


@pytest.mark.parametrize(
    "dandi_path",
    [
        "sub-CGM1/sub-CGM1_ses-CGM1_210125_143404_ecephys.nwb",  # the name the 2022 upload of this pipeline wrote
        "sub-CGM1/sub-CGM1_ses-CGM1-210125-143404_ecephys.nwb",  # the dash name of other files of DANDI:000233
        "sub-CGM1/sub-CGM1_ses-210125_143404_ecephys.nwb",
    ],
)
def test_session_on_dandi_is_found_under_either_name(dandi_path):
    utils = load_module("tingley_metabolic_utils")
    assert utils.get_dandi_session_datetime_key(dandi_path) == utils.get_session_datetime_key("CGM1_210125_143404")


def test_other_sessions_and_files_without_a_session_do_not_match():
    utils = load_module("tingley_metabolic_utils")
    dandi_keys = [
        utils.get_dandi_session_datetime_key(dandi_path)
        for dandi_path in [
            "sub-CGM1/sub-CGM1_ses-CGM1-210125-143404_ecephys.nwb",
            "sub-CGM30/sub-CGM30_ecephys.nwb",
        ]
    ]
    assert utils.get_session_datetime_key("CGM1_210125_143404") in dandi_keys
    assert utils.get_session_datetime_key("CGM1_210126_143404") not in dandi_keys
    assert utils.get_session_datetime_key("CGM30_210123_101500") not in dandi_keys
