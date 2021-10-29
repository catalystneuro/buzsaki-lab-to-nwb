"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
import pandas as pd
from pathlib import Path
import warnings

from lxml import etree as et
from pynwb import NWBFile, TimeSeries
from pynwb.misc import DecompositionSeries
from nwb_conversion_tools import NeuroscopeLFPInterface

from ..utils.band_analysis import filter_lfp, hilbert_lfp
from ..utils.neuroscope import read_lfp, check_module


def get_reference_elec(exp_sheet_path, hilus_csv_path, date, session_id, b=False):
    """Fetch reference electrodes from manual .csv files."""
    df = pd.read_csv(hilus_csv_path)
    if session_id in df["session name"].values:
        return df[df["session name"] == session_id]["hilus Ch"].values[0]

    if b:
        date = date.strftime("%-m/%-d/%Y") + "b"
    try:
        try:
            df1 = pd.read_excel(exp_sheet_path, header=1, sheet_name=1)
            take = df1["implanted"].values == date
            df2 = pd.read_excel(exp_sheet_path, header=3, sheet_name=1)
            out = df2["h"][take[2:]].values[0]
        except:
            df1 = pd.read_excel(exp_sheet_path, header=0, sheet_name=1)
            take = df1["implanted"].values == date
            df2 = pd.read_excel(exp_sheet_path, header=2, sheet_name=1)
            out = df2["h"][take[2:]].values[0]
    except:
        warnings.warn(f"Warning: no channel found in {exp_sheet_path}!")
        return

    #  handle e.g. '7(52below m)'
    if isinstance(out, str):
        digit_stop = np.where([not x.isdigit() for x in out])[0][0]
        if digit_stop:
            return int(out[:digit_stop])
        else:
            print(f"invalid channel for {str(exp_sheet_path)} {str(date)}: {out}")
            return

    return out


class YutaLFPInterface(NeuroscopeLFPInterface):
    """Primary conversion class for LFP data from the SenzaiY dataset."""

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        super().run_conversion(nwbfile=nwbfile, metadata=metadata, stub_test=stub_test)

        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.name
        subject_path = session_path.parent

        xml_filepath = session_path / f"{session_id}.xml"
        root = et.parse(str(xml_filepath)).getroot()
        n_total_channels = int(root.find("acquisitionSystem").find("nChannels").text)
        lfp_sampling_rate = float(root.find("fieldPotentials").find("lfpSamplingRate").text)
        shank_channels = [
            [int(channel.text) for channel in group.find("channels")]
            for group in root.find("spikeDetection").find("channelGroups").findall("group")
        ]
        all_shank_channels = np.concatenate(shank_channels)  # Flattened

        # Special electrodes
        special_electrode_mapping = dict(
            ch_wait=79,
            ch_arm=78,
            ch_solL=76,
            ch_solR=77,
            ch_dig1=65,
            ch_dig2=68,
            ch_entL=72,
            ch_entR=71,
            ch_SsolL=73,
            ch_SsolR=70,
        )
        special_electrodes = []
        for special_electrode_name, channel in special_electrode_mapping.items():
            if channel <= n_total_channels - 1:
                special_electrodes.append(
                    dict(
                        name=special_electrode_name,
                        channel=channel,
                        description="Environmental electrode recorded inline with neural data.",
                    )
                )
        _, all_channels_lfp_data = read_lfp(session_path, stub=stub_test)
        for special_electrode in special_electrodes:
            ts = TimeSeries(
                name=special_electrode["name"],
                description=special_electrode["description"],
                data=all_channels_lfp_data[:, special_electrode["channel"]],
                rate=lfp_sampling_rate,
                unit="V",
                resolution=np.nan,
            )
            nwbfile.add_acquisition(ts)

        # DecompositionSeries
        mouse_number = session_id[-9:-7]
        subject_xls = str(subject_path / f"DGProject/YM{mouse_number} exp_sheet.xlsx")
        hilus_csv_path = str(subject_path / "DGProject/early_session_hilus_chans.csv")
        session_start = metadata["NWBFile"]["session_start_time"]
        if "-" in session_id:
            b = False
        else:
            b = True
        lfp_channel = get_reference_elec(subject_xls, hilus_csv_path, session_start, session_id, b=b)
        if lfp_channel is not None:
            lfp_data = all_channels_lfp_data[:, all_shank_channels]
            all_lfp_phases = []
            for passband in ("theta", "gamma"):
                lfp_fft = filter_lfp(
                    lfp_data[:, all_shank_channels == lfp_channel].ravel(),
                    lfp_sampling_rate,
                    passband=passband,
                )
                lfp_phase, _ = hilbert_lfp(lfp_fft)
                all_lfp_phases.append(lfp_phase[:, np.newaxis])
            decomp_series_data = np.dstack(all_lfp_phases)
            ecephys_mod = check_module(
                nwbfile,
                "ecephys",
                "Intermediate data from extracellular electrophysiology recordings, e.g., LFP.",
            )
            lfp_ts = ecephys_mod.data_interfaces["LFP"]["LFP"]
            decomp_series = DecompositionSeries(
                name="LFPDecompositionSeries",
                description="Theta and Gamma phase for reference LFP",
                data=decomp_series_data,
                rate=lfp_sampling_rate,
                source_timeseries=lfp_ts,
                metric="phase",
                unit="radians",
            )
            # TODO: the band limits should be extracted from parse_passband in band_analysis?
            decomp_series.add_band(band_name="theta", band_limits=(4, 10))
            decomp_series.add_band(band_name="gamma", band_limits=(30, 80))
            check_module(
                nwbfile,
                "ecephys",
                "Contains processed extracellular electrophysiology data.",
            ).add(decomp_series)
