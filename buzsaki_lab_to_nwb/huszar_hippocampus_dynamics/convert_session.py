"""Convert one Huszar et al. 2022 session (DANDI:000552) to NWB."""

from pathlib import Path

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics.converter import HuzsarNWBConverter
from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics.huszarherd import add_external_resources
from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks


def session_to_nwbfile(
    session_dir_path,
    output_dir_path,
    stub_test: bool = False,
    write_lfp: bool = True,
    write_raw: bool = True,
    published_raw_file_path: str = None,
    raw_only: bool = False,
    nwbfile_path: Path = None,
    verbose: bool = False,
) -> Path:
    """Convert one session folder of HuszarR/optotagCA1 (e.g. e13/e13_1m1/e13_1m1_200220); returns the file path."""
    session_dir_path = Path(session_dir_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    session_id = session_dir_path.name
    nwbfile_path = Path(nwbfile_path) if nwbfile_path else output_dir_path / f"{session_id}.nwb"
    nwbfile_path.parent.mkdir(parents=True, exist_ok=True)

    def has(suffix):
        return (session_dir_path / f"{session_id}.{suffix}").is_file()

    folder = dict(folder_path=str(session_dir_path))
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_dir_path),
            write_lfp=write_lfp and not raw_only,
            write_raw=write_raw,
            published_raw_file_path=published_raw_file_path,
        ),
        Epochs=folder,
        OptogeneticPulses=folder,
    )
    if has("spikes.cellinfo.mat"):
        source_data.update(Sorting=folder)
    if has("Behavior.mat") or has("Tracking.Behavior.mat"):
        source_data.update(Position=folder)
    if has("Behavior.mat"):
        source_data.update(BehaviorRewards=folder, Trials=folder)
    if has("SleepState.states.mat"):
        source_data.update(BehaviorSleep=folder)
    if has("ripples.events.mat"):
        source_data.update(RippleEvents=folder)
    if not has("pulses.events.mat"):
        source_data.pop("OptogeneticPulses")

    if (
        raw_only
    ):  # the session's raw file: electrodes, epochs and the wide-band signal; the rest is in its processed file
        source_data = dict(Ecephys=source_data["Ecephys"], Epochs=source_data["Epochs"])

    converter = HuzsarNWBConverter(source_data=source_data, verbose=verbose)
    metadata = dict_deep_update(converter.get_metadata(), load_dict_from_file(Path(__file__).parent / "metadata.yml"))
    conversion_options = dict(Ecephys=dict(stub_test=stub_test))
    nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
    add_external_resources(nwbfile)
    add_value_meanings(nwbfile, load_dict_from_file(Path(__file__).parent / "value_meanings.yaml"))
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    set_streaming_chunks(backend_configuration)
    configure_and_write_nwbfile(
        nwbfile=nwbfile, nwbfile_path=str(nwbfile_path), backend_configuration=backend_configuration
    )
    return nwbfile_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session_dir_path", type=Path, help="session folder, e.g. optotagCA1/e13/e13_1m1/e13_1m1_200220"
    )
    parser.add_argument("output_dir_path", type=Path)
    parser.add_argument("--stub", action="store_true", help="only the first samples of the LFP and wide-band signal")
    parser.add_argument("--no-lfp", action="store_true", help="leave out the .lfp file")
    parser.add_argument("--no-raw", action="store_true", help="leave out the wide-band .dat file")
    parser.add_argument("--published-raw", help="wide-band signal from the session's earlier raw file: a path or URL")
    parser.add_argument("--raw-only", action="store_true", help="write only the electrodes and wide-band signal")
    parser.add_argument("--nwbfile-path", type=Path, help="the output file (default OUTPUT_DIR/SESSION.nwb)")
    args = parser.parse_args()
    print(
        session_to_nwbfile(
            args.session_dir_path,
            args.output_dir_path,
            stub_test=args.stub,
            write_lfp=not args.no_lfp,
            write_raw=not args.no_raw,
            published_raw_file_path=args.published_raw,
            raw_only=args.raw_only,
            nwbfile_path=args.nwbfile_path,
        )
    )
