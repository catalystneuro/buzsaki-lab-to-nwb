"""Primary script to run to convert an entire session of data using the NWBConverter."""
import time
from pathlib import Path
from warnings import warn

from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.valero.converter import ValeroNWBConverter


def session_to_nwbfile(
    session_dir_path, output_dir_path, iterator_opts=None, stub_test=False, write_electrical_series=True, verbose=False
):
    iterator_opts = dict() if iterator_opts is None else iterator_opts
    if verbose:
        start_time = time.time()
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

    if not write_electrical_series:
        nwbfile_path = output_dir_path / f"{session_id}_no_raw_data.nwb"

    source_data = dict()
    conversion_options = dict()

    # Add Recording
    file_path = session_dir_path / f"{session_id}.dat"
    folder_path = session_dir_path
    raw_recording_file_available = file_path.is_file()
    if raw_recording_file_available:
        if verbose:
            size_in_GB = file_path.stat().st_size / 1000**3
            print(f"The size of {file_path.name} is {size_in_GB} GB")
        source_data.update(Recording=dict(folder_path=str(folder_path), verbose=verbose))
        conversion_options.update(
            Recording=dict(
                stub_test=stub_test,
                iterator_opts=iterator_opts,
                write_electrical_series=write_electrical_series,
            )
        )
    else:
        warn(f"Skipping recording interface for {session_id} because the file {file_path} does not exist.")

    # Add LFP
    file_path = session_dir_path / f"{session_id}.lfp"
    folder_path = session_dir_path
    lfp_file_available = file_path.is_file()
    if lfp_file_available:
        if verbose:
            size_in_GB = file_path.stat().st_size / 1000**3
            print(f"The size of {file_path.name} is {size_in_GB} GB")

        source_data.update(LFP=dict(folder_path=str(folder_path), verbose=verbose))
        conversion_options.update(
            LFP=dict(
                stub_test=stub_test,
                iterator_opts=iterator_opts,
                write_electrical_series=write_electrical_series,
            )
        )
    else:
        warn(f"Skipping LFP interface for {session_id} because the file {file_path} does not exist.")

    # Add sorter
    write_ecephys_metadata = (not raw_recording_file_available) and (not lfp_file_available)
    file_path = session_dir_path / f"{session_id}.spikes.cellinfo.mat"
    source_data.update(Sorting=dict(file_path=str(file_path), verbose=verbose))
    conversion_options.update(Sorting=dict(write_ecephys_metadata=write_ecephys_metadata))

    # Add videos
    folder_path = session_dir_path
    source_data.update(Video=dict(folder_path=str(folder_path)))
    conversion_options.update(Video=dict(stub_test=stub_test, external_mode=True))

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
    source_data.update(RippleEvents=dict(folder_path=str(folder_path), verbose=verbose))

    # Add HSE events
    folder_path = session_dir_path
    source_data.update(HSEvents=dict(folder_path=str(folder_path), verbose=verbose))

    # Add UP and Down events
    folder_path = session_dir_path
    source_data.update(UPDownEvents=dict(folder_path=str(folder_path), verbose=verbose))

    # Add sleep states
    folder_path = session_dir_path
    source_data.update(BehaviorSleepStates=dict(folder_path=str(folder_path), verbose=verbose))

    # Build the converter
    converter = ValeroNWBConverter(source_data=source_data, session_folder_path=str(session_dir_path), verbose=verbose)

    # Update default metadata with the one in the editable yaml file in this directory
    metadata = converter.get_metadata()
    editable_metadata_path = Path(__file__).parent / "metadata.yml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    session_id_to_write = metadata["NWBFile"]["session_id"]
    if not write_electrical_series:
        session_id_to_write += "_no_raw_data"
        metadata["NWBFile"]["session_id"] = session_id_to_write

    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
    if verbose:
        end_time = time.time()
        conversion_time = end_time - start_time
        print(f"Conversion for session {session_id} done in {conversion_time / 60.0 :,.2f} minutes!")
        print(f"File saved to {nwbfile_path}")

    return nwbfile_path


if __name__ == "__main__":
    # Parameters for conversion
    stub_test = False  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    iterator_opts = dict(buffer_gb=20.0, display_progress=verbose)

    write_electrical_series = False  # Write the electrical series to the NWB file
    output_dir_path = Path.home() / "conversion_nwb"
    project_root_path = Path("/media/heberto/One Touch/Buzsaki/ValeroM/")
    subject_path = project_root_path / "fCamk1"
    # subject_path = project_root_path / "fCamk2"
    subject_path = project_root_path / "fcamk3"
    # subject_path = project_root_path / "fcamk5"
    session_dir_path = subject_path / "fCamk3_201105_sess16"

    nwbfile_path = session_to_nwbfile(
        session_dir_path,
        output_dir_path,
        iterator_opts=iterator_opts,
        stub_test=stub_test,
        write_electrical_series=write_electrical_series,
        verbose=verbose,
    )

    # import pandas as pd
    # from pynwb import NWBHDF5IO

    # nwbfile = NWBHDF5IO(nwbfile_path, "r").read()

    # dataframe = nwbfile.electrodes.to_dataframe()
    # # Show all the entries of the dataframe
    # with pd.option_context("display.max_rows", None, "display.max_columns", None):
    #     print(dataframe)
