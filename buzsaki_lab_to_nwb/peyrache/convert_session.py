"""Convert one Peyrache et al. 2015 session (DANDI:000056, CRCNS th-1) to NWB."""

from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.peyrache import PeyracheNWBConverter
from buzsaki_lab_to_nwb.peyrache.peyracheherd import add_external_resources
from buzsaki_lab_to_nwb.peyrache.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    session_info_file_path: Optional[Path] = None,
    published_nwb_file_path: Optional[Path] = None,
    stub_test: bool = False,
):
    """Convert one session folder (a copy of PeyracheA/MouseNN/MouseNN-YYMMDD of the Buzsaki lab share).

    `session_info_file_path` is the CRCNS th-1 session table (crcns_th-1_session_info.xls, for the probe depths).
    `published_nwb_file_path` is the session's file from DANDI:000056 version 0.250624.0430, the source of the LFP.
    The mouse folder (the parent of the session folder, or a sibling folder named after the mouse) is searched for the
    .pos/.ang files that some sessions keep there.
    """
    session_path = Path(session_path)
    mouse = session_path.name.split("-")[0]
    mouse_folder_path = next(
        (path for path in (session_path.parent, session_path.parent / mouse) if path.name == mouse and path.is_dir()),
        None,
    )
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            session_info_file_path=str(session_info_file_path) if session_info_file_path else None,
            published_nwb_file_path=str(published_nwb_file_path) if published_nwb_file_path else None,
        ),
        Sorting=dict(folder_path=str(session_path)),
        Behavior=dict(
            folder_path=str(session_path), mouse_folder_path=str(mouse_folder_path) if mouse_folder_path else None
        ),
    )
    converter = PeyracheNWBConverter(source_data=source_data)
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
    parser.add_argument("session_path", type=Path, help="session folder, e.g. PeyracheA/Mouse12/Mouse12-120807")
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--session-info", type=Path, help="crcns_th-1_session_info.xls")
    parser.add_argument("--published", type=Path, help="the session's file from DANDI:000056 version 0.250624.0430")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.nwbfile_path, args.session_info, args.published, args.stub)
