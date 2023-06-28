"""Primary script to run to convert an entire session of data using the NWBConverter."""

from neuroconv.utils import load_dict_from_file, dict_deep_update
from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics import HuzsarNWBConverter
from pathlib import Path

def session_to_nwbfile(session_dir_path, output_dir_path, stub_test=False, write_electrical_series=True, verbose=False):
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
    conversion_options = dict()

    # Add Recordings
    file_path = session_dir_path / f"{session_id}.dat"
    xml_file_path = session_dir_path / f"{session_id}.xml"
    raw_recording_file_available = file_path.is_file()

    if file_path.is_file():
        size_in_GB = file_path.stat().st_size / 1000
        if size_in_GB:
            if verbose:
                print(f"The size of {file_path.name} is {size_in_GB} GB")
            source_data.update(Recording=dict(file_path=str(file_path), xml_file_path=str(xml_file_path)))
            conversion_options.update(
                Recording=dict(stub_test=stub_test, write_electrical_series=write_electrical_series)
            )
        else:
            print(f"Skipping recording interface for {session_id} because the file {file_path} does not have any data.")

    else:
        print(f"Skipping recording interface for {session_id} because the file {file_path} does not exist.")

    # Add LFP
    file_path = session_dir_path / f"{session_id}.lfp"
    folder_path = session_dir_path
    lfp_file_available = file_path.is_file()

    if file_path.is_file():
        size_in_GB = file_path.stat().st_size / 1000**3

        if size_in_GB:
            if verbose:
                print(f"The size of {file_path.name} is {size_in_GB} GB")

            source_data.update(LFP=dict(file_path=str(file_path), xml_file_path=str(xml_file_path)))
            conversion_options.update(LFP=dict(stub_test=stub_test, write_electrical_series=write_electrical_series))

        else:
            print(f"Skipping LFP interface for {session_id} because the file {file_path} does not have any data.")

    else:
        print(f"Skipping LFP interface for {session_id} because the file {file_path} does not exist.")

    write_ecephys_metadata = (not raw_recording_file_available) and (not lfp_file_available)

    # Add sorter
    file_path = session_dir_path / f"{session_id}.spikes.cellinfo.mat"
    source_data.update(Sorting=dict(file_path=str(file_path), verbose=verbose))
    conversion_options.update(Sorting=dict(write_ecephys_metadata=write_ecephys_metadata))

    # Add behavior data
    source_data.update(Behavior8Maze=dict(folder_path=str(session_dir_path)))
    conversion_options.update(Behavior8Maze=dict(stub_test=stub_test))

    source_data.update(BehaviorSleep=dict(folder_path=str(session_dir_path)))

    # Add epochs
    source_data.update(Epochs=dict(folder_path=str(session_dir_path)))

    # Add trials
    source_data.update(Trials=dict(folder_path=str(session_dir_path)))

    # Add linear track behavior
    source_data.update(Behavior8Maze=dict(folder_path=str(session_dir_path)))

    # Add reward events in linear track
    source_data.update(BehaviorRewards=dict(folder_path=str(session_dir_path)))

    # Add ripple events
    source_data.update(RippleEvents=dict(folder_path=str(session_dir_path)))

    # Build the converter
    converter = HuzsarNWBConverter(source_data=source_data, verbose=verbose)

    # Session start time (missing time, only the date part)
    metadata = converter.get_metadata()

    # Update default metadata with the one in the editable yaml file in this directory
    editable_metadata_path = Path(__file__).parent / "metadata.yml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    # Run conversion
    nwbfile = converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )

    return nwbfile


if __name__ == "__main__":
    # Parameters for conversion
    stub_test = True  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    output_dir_path = Path.home() / "conversion_nwb"
    project_root = Path("/shared/catalystneuro/HuszarR/optotagCA1")
    session_dir_path = project_root / "e13" / "e13_26m1" / "e13_26m1_211119"
    assert session_dir_path.is_dir()
    nwbfile = session_to_nwbfile(session_dir_path, output_dir_path, stub_test=stub_test, verbose=verbose)
