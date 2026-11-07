"""Convert one Tingley and Buzsaki session (DANDI:000213 or DANDI:000218) to NWB."""

from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.tingley_septal import TingleyNWBConverter
from buzsaki_lab_to_nwb.tingley_septal.tingleyherd import add_external_resources
from buzsaki_lab_to_nwb.tingley_septal.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks

DANDISETS = ("000213", "000218")


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    dandiset: str,
    published_nwb_file_path: Optional[Path] = None,
    include_wideband: bool = True,
    stub_test: bool = False,
):
    """Convert one session folder (e.g. TingleyD/DT8/20170207_144um_1944um_merge).

    `dandiset` picks the paper's metadata: 000213 (Tingley and Buzsaki 2018) or 000218 (Tingley and Buzsaki 2020).
    `published_nwb_file_path` is the session's file from the earlier version of either dandiset, the source of the
    LFP and the wide-band signal (the lab's .lfp and .dat files are not on the public share).
    """
    if dandiset not in DANDISETS:
        raise ValueError(f"dandiset must be one of {DANDISETS}")
    session_path = Path(session_path)
    folder = dict(folder_path=str(session_path))
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            published_nwb_file_path=str(published_nwb_file_path) if published_nwb_file_path else None,
            include_wideband=include_wideband,
        ),
        Sorting=folder,
        Behavior=folder,
        Events=folder,
    )
    converter = TingleyNWBConverter(source_data=source_data)
    metadata = dict_deep_update(
        converter.get_metadata(), load_dict_from_file(Path(__file__).parent / f"metadata_{dandiset}.yml")
    )
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
    parser.add_argument("session_path", type=Path, help="session folder, e.g. TingleyD/DT8/20170207_144um_1944um_merge")
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--dandiset", choices=DANDISETS, required=True)
    parser.add_argument("--published", help="the session's file from the earlier dandiset version (LFP): a path or a URL")
    parser.add_argument("--no-wideband", action="store_true", help="leave out the 20 kHz signal")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.nwbfile_path, args.dandiset, args.published, not args.no_wideband, args.stub)
