"""Convert one Valero et al. 2022 session (DANDI:000568) to NWB."""

from pathlib import Path

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import load_dict_from_file

from buzsaki_lab_to_nwb.valero.converter import ValeroNWBConverter
from buzsaki_lab_to_nwb.valero.valeroherd import add_external_resources
from buzsaki_lab_to_nwb.valero.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks

FOLDER_INTERFACES = [
    "Ecephys",
    "Sorting",
    "Epochs",
    "Trials",
    "OptogeneticStimuli",
    "BehaviorLinearTrack",
    "BehaviorLinearTrackRewards",
    "BehaviorSleepStates",
    "RippleEvents",
    "HSEvents",
    "UPDownEvents",
    "Video",
]


def session_to_nwbfile(
    session_dir_path,
    output_dir_path,
    stub_test: bool = False,
    write_electrical_series: bool = True,
    write_lfp: bool = True,
    verbose: bool = False,
) -> Path:
    """Convert a session folder of the lab's ValeroM copy.

    The tested source is the copy the 2023 conversion used (Google Drive, ValeroM/<mouse>/<session>; fCamk3 sess13 is
    nested in the sess12 folder there), which matches the published units and ripples. The Globus share
    (ValeroM/unindexedSubjets) has later versions of some files (e.g. a 48-unit re-sorting of fCamk3 sess13).

    With `write_electrical_series=False` the wide-band signal is left out and the file is named `<session>_no_raw_data`.
    """
    session_dir_path = Path(session_dir_path)
    output_dir_path = Path(output_dir_path) / ("nwb_stub" if stub_test else "")
    output_dir_path.mkdir(parents=True, exist_ok=True)
    session_id = session_dir_path.name
    nwbfile_path = output_dir_path / f"{session_id}{'' if write_electrical_series else '_no_raw_data'}.nwb"

    source_data = {name: dict(folder_path=str(session_dir_path)) for name in FOLDER_INTERFACES}
    converter = ValeroNWBConverter(source_data=source_data, session_folder_path=str(session_dir_path), verbose=verbose)
    metadata = converter.get_metadata()
    conversion_options = {name: dict(stub_test=stub_test) for name in FOLDER_INTERFACES}
    conversion_options["Ecephys"].update(write_raw=write_electrical_series, write_lfp=write_lfp)
    conversion_options["Video"].update(nwbfile_path=str(nwbfile_path))

    nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
    add_external_resources(nwbfile)
    add_value_meanings(nwbfile, load_dict_from_file(Path(__file__).parent / "value_meanings.yaml"))
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    set_streaming_chunks(backend_configuration)
    configure_and_write_nwbfile(
        nwbfile=nwbfile, nwbfile_path=str(nwbfile_path), backend_configuration=backend_configuration
    )
    if verbose:
        print(f"File saved to {nwbfile_path}")
    return nwbfile_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir_path", type=Path, help="session folder, e.g. ValeroM/fCamk1/fCamk1_200827_sess9")
    parser.add_argument("output_dir_path", type=Path)
    parser.add_argument("--stub", action="store_true")
    parser.add_argument("--no-raw", action="store_true", help="leave out the wide-band signal (.dat)")
    parser.add_argument("--no-lfp", action="store_true", help="leave out the LFP (.lfp)")
    args = parser.parse_args()
    session_to_nwbfile(
        args.session_dir_path,
        args.output_dir_path,
        stub_test=args.stub,
        write_electrical_series=not args.no_raw,
        write_lfp=not args.no_lfp,
        verbose=True,
    )
