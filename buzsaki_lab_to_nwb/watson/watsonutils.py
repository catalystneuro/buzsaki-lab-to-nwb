"""Helpers for reading the Neuroscope and buzcode files of the Watson sessions."""

from pathlib import Path

import numpy as np
from lxml import etree
from pymatreader import read_mat
from scipy.signal import butter, filtfilt, hilbert


def read_session_xml(xml_file_path: Path) -> dict:
    """Read the acquisition settings and channel layout from a Neuroscope .xml file."""
    root = etree.parse(str(xml_file_path)).getroot()
    acquisition = root.find("acquisitionSystem")
    shank_channels = [
        [int(channel.text) for channel in group.find("channels")]
        for group in root.find("spikeDetection").find("channelGroups").findall("group")
    ]
    return dict(
        n_channels=int(acquisition.find("nChannels").text),
        sampling_rate=float(acquisition.find("samplingRate").text),
        n_bits=int(acquisition.find("nBits").text),
        voltage_range=float(acquisition.find("voltageRange").text),
        amplification=float(acquisition.find("amplification").text),
        lfp_sampling_rate=float(root.find("fieldPotentials").find("lfpSamplingRate").text),
        spikes_n_samples=int(root.find("neuroscope").find("spikes").find("nSamples").text),
        shank_channels=shank_channels,
    )


def get_conversion_to_volts(xml_info: dict) -> float:
    """Volts per int16 step: the ADC voltage range divided by its levels and by the amplifier gain."""
    return xml_info["voltage_range"] / 2 ** xml_info["n_bits"] / xml_info["amplification"]


def read_basic_metadata(file_path: Path) -> dict:
    """Read the reference channels and cortical region from a _BasicMetaData.mat file."""
    mat = read_mat(str(file_path))
    bmd = mat["bmd"]
    return dict(
        up_reference=int(bmd["UPstatechannel"]),
        spindle_reference=int(bmd["Spindlechannel"]),
        theta_reference=int(bmd["Thetachannel"]),
        cortex_region=str(mat["CortexRegion"]),
    )


def bandpass_phase(signal: np.ndarray, sampling_rate: float, band: tuple, order: int = 4) -> np.ndarray:
    """Phase in [0, 2*pi) of the Hilbert transform of a zero-phase Butterworth band-passed signal."""
    b, a = butter(order, np.array(band) / (sampling_rate / 2), "bandpass")
    filtered = filtfilt(b, a, signal)
    # hilbert runs much faster on a power of 2
    n_fft = 1 if len(filtered) == 0 else 2 ** (len(filtered) - 1).bit_length()
    return np.mod(np.angle(hilbert(filtered, n_fft)[: len(filtered)]), 2 * np.pi)
