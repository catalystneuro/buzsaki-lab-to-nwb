"""Convert one Petersen and Buzsaki 2020 session (DANDI:000059) to NWB."""

from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.petersen import PetersenNWBConverter
from buzsaki_lab_to_nwb.petersen.petersenherd import add_external_resources
from buzsaki_lab_to_nwb.petersen.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    published_raw_file_path: Optional[Path] = None,
    include_wideband: bool = True,
    stub_test: bool = False,
):
    """Convert one session folder (PetersenP/<rat>/<session> on the Buzsaki lab share).

    `published_raw_file_path` is the session's "desc-raw" file from DANDI:000059 version 0.250624.0444, the source of
    the LFP and wide-band signal (the lab's .lfp and .dat files are not on the share for most sessions).
    """
    session_path = Path(session_path)
    session_id = session_path.name
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            published_raw_file_path=str(published_raw_file_path) if published_raw_file_path else None,
            include_wideband=include_wideband,
        ),
        Behavior=dict(folder_path=str(session_path)),
    )
    phy_folders = sorted(path for path in session_path.glob("Kilosort_*") if (path / "spike_times.npy").is_file())
    if len(phy_folders) > 1:
        # Sorted more than once: the sorting the lab's cell metrics were computed from (general.clusteringpath)
        from buzsaki_lab_to_nwb.petersen.petersenutils import read_mat

        metrics_file_path = session_path / f"{session_id}.cell_metrics.cellinfo.mat"
        used = None
        if metrics_file_path.is_file():
            general = read_mat(metrics_file_path)["cell_metrics"].get("general", {})
            used = Path(str(general.get("clusteringpath", ""))).name if isinstance(general, dict) else None
        chosen = [path for path in phy_folders if path.name == used]
        if not chosen:
            raise ValueError(f"{session_id} has more than one Kilosort folder: {[path.name for path in phy_folders]}")
        phy_folders = chosen
    if phy_folders:
        source_data.update(Sorting=dict(folder_path=str(session_path), phy_folder_path=str(phy_folders[0])))

    converter = PetersenNWBConverter(source_data=source_data)
    metadata = dict_deep_update(converter.get_metadata(), load_dict_from_file(Path(__file__).parent / "metadata.yml"))
    conversion_options = dict(Ecephys=dict(stub_test=stub_test))
    if phy_folders:
        conversion_options.update(Sorting=dict(stub_test=stub_test))
    nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
    add_external_resources(nwbfile)
    add_value_meanings(nwbfile, load_dict_from_file(Path(__file__).parent / "value_meanings.yaml"))
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    set_streaming_chunks(backend_configuration)
    configure_and_write_nwbfile(
        nwbfile=nwbfile, nwbfile_path=str(nwbfile_path), backend_configuration=backend_configuration
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session_path", type=Path, help="session folder, e.g. PetersenP/MS21/Peter_MS21_180719_155941_concat"
    )
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--published-raw", type=Path, help="the session's desc-raw file from DANDI:000059")
    parser.add_argument("--no-wideband", action="store_true", help="write the LFP but not the wide-band signal")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.nwbfile_path, args.published_raw, not args.no_wideband, args.stub)
