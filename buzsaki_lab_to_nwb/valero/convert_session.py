"""Primary script to run to convert an entire session of data using the NWBConverter."""
from pathlib import Path

from neuroconv.utils import load_dict_from_file, dict_deep_update

from buzsaki_lab_to_nwb.valero.converter import ValeroNWBConverter


def session_to_nwb(session_dir_path, output_dir_path, stub_test=False, verbose=False):
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

    # Add Recording
    file_path = session_dir_path / f"{session_id}.dat"
    assert file_path.is_file()
    xml_file_path = session_dir_path / f"{session_id}.xml"
    source_data.update(Recording=dict(file_path=str(file_path), xml_file_path=str(xml_file_path)))

    file_path = session_dir_path / f"{session_id}.lfp"
    assert file_path.is_file()
    source_data.update(LFP=dict(file_path=str(file_path), xml_file_path=str(xml_file_path)))

    # Add sorter
    file_path = session_dir_path / f"{session_id}.spikes.cellinfo.mat"
    source_data.update(Sorting=dict(file_path=str(file_path), sampling_frequency=30_000.0))

    # Build the converter
    converter = ValeroNWBConverter(source_data=source_data, verbose=verbose)

    # Session start time (missing time, only the date part)
    metadata = converter.get_metadata()

    # Update default metadata with the one in the editable yaml file in this directory
    editable_metadata_path = Path(__file__).parent / "metadata.yml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    # Set conversion options and run conversion
    conversion_options = dict(
        Recording=dict(stub_test=stub_test),
        LFP=dict(stub_test=stub_test),
    )
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )


if __name__ == "__main__":
    # Parameters for conversion
    stub_test = True  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    output_dir_path = Path.home() / "conversion_nwb"
    project_root = Path("/home/heberto/buzaki")
    session_dir_path = project_root / "fCamk1_200827_sess9"
    session_to_nwb(session_dir_path, output_dir_path, stub_test=stub_test, verbose=verbose)
