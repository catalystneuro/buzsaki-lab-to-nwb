"""Primary script to run to convert an entire session of data using the NWBConverter."""
import datetime
import warnings
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics import HuzsarNWBConverter


def session_to_nwb(session_dir_path, output_dir_path, stub_test=False, verbose=False):
    if verbose:
        print("---------------------")
        print("conversion for:")
        print(f"{session_dir_path=}")

    session_dir_path = Path(session_dir_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    session_id = session_dir_path.stem
    nwbfile_path = output_dir_path / f"{session_id}.nwb"

    source_data = dict()
    # Add sorter
    file_path = session_dir_path / f"{session_id}.spikes.cellinfo.mat"
    source_data.update(Sorting=dict(file_path=str(file_path), sampling_frequency=30_000.0))

    # Add behavior data
    source_data.update(Behavior8Maze=dict(folder_path=str(session_dir_path)))
    source_data.update(BehaviorSleep=dict(folder_path=str(session_dir_path)))
    source_data.update(Electrodes=dict(folder_path=str(session_dir_path)))

    # Build the converter
    converter = HuzsarNWBConverter(source_data=source_data, verbose=verbose)

    # Session start time (missing time, only the date part)
    metadata = converter.get_metadata()

    # Update default metadata with the one in the editable yaml file in this directory
    editable_metadata_path = Path(__file__).parent / "metadata.yml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    # Set conversion options and run conversion
    conversion_options = dict(
        Behavior8Maze=dict(stub_test=stub_test),
    )
    nwbfile = converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )

    return nwbfile


if __name__ == "__main__":
    # Parameters for conversion
    stub_test = False  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    output_dir_path = Path.home() / "conversion_nwb"
    project_root = Path("/media/heberto/One Touch/Buzsaki/optotagCA1")
    session_dir_path = project_root / "e13" / "e13_16f1" / "e13_16f1_210302"
    assert session_dir_path.is_dir()
    nwbfile = session_to_nwb(session_dir_path, output_dir_path, stub_test=stub_test, verbose=verbose)

    # import pandas as pd
    # # Open the NWB file from output_dir_path
    # from pynwb import NWBHDF5IO
    # nwbfile = NWBHDF5IO(output_dir_path / f"{session_dir_path.name}.nwb", "r").read()

    # dataframe = nwbfile.electrodes.to_dataframe()
    # # Show all the entries of the dataframe
    # with pd.option_context("display.max_rows", None, "display.max_columns", None):
    #     print(dataframe)
