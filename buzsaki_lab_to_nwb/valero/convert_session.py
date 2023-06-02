"""Primary script to run to convert an entire session of data using the NWBConverter."""
from pathlib import Path

from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.valero.converter import ValeroNWBConverter


def session_to_nwbfile(session_dir_path, output_dir_path, stub_test=False, write_electrical_series=True, verbose=False):
    if verbose:
        print("---------------------")
        print("conversion for:")
        print(f"{session_dir_path=}")

    session_dir_path = Path(session_dir_path)
    assert session_dir_path.is_dir()
    output_dir_path = Path(output_dir_path)

    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    session_id = session_dir_path.stem
    nwbfile_path = output_dir_path / f"{session_id}.nwb"

    source_data = dict()
    conversion_options = dict()

    # Add Recording
    file_path = session_dir_path / f"{session_id}.dat"
    assert file_path.is_file()
    xml_file_path = session_dir_path / f"{session_id}.xml"
    folder_path = session_dir_path
    source_data.update(
        Recording=dict(file_path=str(file_path), xml_file_path=str(xml_file_path), folder_path=str(folder_path))
    )
    conversion_options.update(Recording=dict(stub_test=stub_test, write_electrical_series=write_electrical_series))

    # Add LFP
    file_path = session_dir_path / f"{session_id}.lfp"
    assert file_path.is_file()
    xml_file_path = session_dir_path / f"{session_id}.xml"
    folder_path = session_dir_path
    source_data.update(
        LFP=dict(file_path=str(file_path), xml_file_path=str(xml_file_path), folder_path=str(folder_path))
    )
    conversion_options.update(LFP=dict(stub_test=stub_test, write_electrical_series=write_electrical_series))

    # Add sorter
    file_path = session_dir_path / f"{session_id}.spikes.cellinfo.mat"
    source_data.update(Sorting=dict(file_path=str(file_path), sampling_frequency=30_000.0))

    # Add videos
    file_paths = list(session_dir_path.rglob("*.avi"))
    assert len(file_paths) == 1, f"There should be one and only one video file {file_paths}"
    source_data.update(Video=dict(file_paths=file_paths))
    conversion_options.update(Video=dict(stub_test=stub_test))

    # Add epochs
    folder_path = session_dir_path
    source_data.update(Epochs=dict(folder_path=str(folder_path)))

    # Add trials
    folder_path = session_dir_path
    source_data.update(Trials=dict(folder_path=str(folder_path)))

    # Add laser pulses
    folder_path = session_dir_path
    source_data.update(OptogeneticStimuli=dict(folder_path=str(folder_path)))

    # Add linear track behavior
    folder_path = session_dir_path
    source_data.update(BehaviorLinearTrack=dict(folder_path=str(folder_path)))

    # Add reward events in linear track
    folder_path = session_dir_path
    source_data.update(BehaviorLinearTrackRewards=dict(folder_path=str(folder_path)))

    # Add ripple events
    folder_path = session_dir_path
    source_data.update(RippleEvents=dict(folder_path=str(folder_path)))

    # Add HSE events
    folder_path = session_dir_path
    source_data.update(HSEvents=dict(folder_path=str(folder_path)))

    # Add UP and Down events
    folder_path = session_dir_path
    source_data.update(UPDownEvents=dict(folder_path=str(folder_path)))

    # Add sleep states
    folder_path = session_dir_path
    source_data.update(BehaviorSleepStates=dict(folder_path=str(folder_path)))

    # Build the converter
    converter = ValeroNWBConverter(source_data=source_data, verbose=verbose)

    # Session start time (missing time, only the date part)
    metadata = converter.get_metadata()

    # Update default metadata with the one in the editable yaml file in this directory
    editable_metadata_path = Path(__file__).parent / "metadata.yml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

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
    write_electrical_series = True  # Write the electrical series to the NWB file
    output_dir_path = Path.home() / "conversion_nwb"
    project_root = Path("/home/heberto/buzaki")
    session_dir_path = project_root / "fCamk1_200827_sess9"
    session_dir_path = project_root / "fCamk2" / "fCamk2_201012_sess1"
    session_dir_path = project_root / "fCamk2" / "fCamk2_201013_sess2"

    nwbfile = session_to_nwbfile(
        session_dir_path,
        output_dir_path,
        stub_test=stub_test,
        write_electrical_series=write_electrical_series,
        verbose=verbose,
    )

    dataframe = nwbfile.electrodes.to_dataframe()
    import pandas as pd

    # Show all the entries of the dataframe
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(dataframe)

    unique_channels = dataframe.channel_name.unique()
    print(f"Unique channels size: {len(unique_channels)}")
    print(unique_channels)
    print(dataframe.loc[dataframe["channel_name"] == "ch20grp0"])
