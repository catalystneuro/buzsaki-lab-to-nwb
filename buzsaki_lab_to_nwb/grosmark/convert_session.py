"""Convert one Grosmark and Buzsaki 2016 session (DANDI:000044) to NWB."""

from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.grosmark import GrosmarkNWBConverter
from buzsaki_lab_to_nwb.grosmark.grosmarkherd import add_external_resources
from buzsaki_lab_to_nwb.grosmark.grosmarkutils import split_session_id
from buzsaki_lab_to_nwb.grosmark.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks


def find_pre_meta_file(session_path: Path) -> Optional[Path]:
    """The Amplipex .meta file of the session's PRE recording, in the rat's raw-data folder (e.g. Achilles/Achilles151)."""
    rat, date = split_session_id(session_path.name)
    for meta_file_path in sorted(session_path.parent.glob(f"{rat}*/{rat}*_{date:%m%d%Y}_pre*.meta")):
        return meta_file_path
    return None


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    published_nwb_file_path: Optional[Path] = None,
    clu_res_folder_path: Optional[Path] = None,
    stub_test: bool = False,
):
    """Convert one session folder (e.g. GrosmarkAD/Gatsby/Gatsby_08282013).

    The folder holds the session's .xml, _sessInfo.mat, .SleepState.states.mat and .eeg files, and position_info.mat
    for the linear-track sessions that have one. Without the .eeg file, the LFP is taken from
    `published_nwb_file_path`, the session's file from an earlier version of DANDI:000044, and the EMG and
    accelerometer are left out. `clu_res_folder_path` holds the session's .clu and .res files, to check the units
    against (default: the session folder, if they are there).
    """
    session_path = Path(session_path)
    session_id = session_path.name
    eeg_file_path = session_path / f"{session_id}.eeg"
    laps_file_path = session_path / "position_info.mat"
    if clu_res_folder_path is None and (session_path / f"{session_id}.res.1").is_file():
        clu_res_folder_path = session_path
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            eeg_file_path=str(eeg_file_path) if eeg_file_path.is_file() else None,
            published_nwb_file_path=str(published_nwb_file_path) if published_nwb_file_path else None,
        ),
        Sorting=dict(
            folder_path=str(session_path),
            clu_res_folder_path=str(clu_res_folder_path) if clu_res_folder_path else None,
        ),
        Behavior=dict(
            folder_path=str(session_path),
            laps_file_path=str(laps_file_path) if laps_file_path.is_file() else None,
        ),
    )
    converter = GrosmarkNWBConverter(source_data=source_data, meta_file_path=find_pre_meta_file(session_path))
    metadata = dict_deep_update(converter.get_metadata(), load_dict_from_file(Path(__file__).parent / "metadata.yml"))
    conversion_options = dict(Ecephys=dict(stub_test=stub_test), Sorting=dict(stub_test=stub_test))
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
    parser.add_argument("session_path", type=Path, help="session folder, e.g. GrosmarkAD/Gatsby/Gatsby_08282013")
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--published", type=Path, help="the session's file from DANDI:000044, for the LFP")
    parser.add_argument("--clu-res", type=Path, help="folder with the session's .clu and .res files")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.nwbfile_path, args.published, args.clu_res, args.stub)
