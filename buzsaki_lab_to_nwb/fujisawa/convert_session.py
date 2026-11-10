"""Convert one Fujisawa et al. 2008 session (DANDI:000067) to NWB."""

from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.fujisawa.fujisawaherd import add_external_resources
from buzsaki_lab_to_nwb.fujisawa.fujisawanwbconverter import FujisawaNWBConverter
from buzsaki_lab_to_nwb.fujisawa.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    published_nwb_file_path: Optional[Path] = None,
    dat_file_path: Optional[Path] = None,
    stub_test: bool = False,
):
    """Convert one session folder.

    `published_nwb_file_path` is the session's file from an earlier version of DANDI:000067, the source of the LFP and
    wide-band signal; `dat_file_path` the lab's wide-band .dat file, for sessions with no earlier file.
    """
    session_path = Path(session_path)
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            published_nwb_file_path=str(published_nwb_file_path) if published_nwb_file_path else None,
            dat_file_path=str(dat_file_path) if dat_file_path else None,
        ),
        Sorting=dict(folder_path=str(session_path)),
        Behavior=dict(folder_path=str(session_path)),
    )
    converter = FujisawaNWBConverter(source_data=source_data)
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
    parser.add_argument("session_path", type=Path, help="session folder, e.g. EE/EE0627fm/Subsessions/EE.088")
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--published", type=Path, help="the session's file from DANDI:000067")
    parser.add_argument("--dat", type=Path, help="the lab's wide-band .dat file")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.nwbfile_path, args.published, args.dat, args.stub)
