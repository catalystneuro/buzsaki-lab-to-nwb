"""Convert one Girardeau et al. 2017 session (DANDI:000061) to NWB."""

import os
from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file
from pynwb.image import ImageSeries

from buzsaki_lab_to_nwb.girardeau import GirardeauNWBConverter
from buzsaki_lab_to_nwb.girardeau.girardeauherd import add_external_resources
from buzsaki_lab_to_nwb.girardeau.value_meanings import add_value_meanings
from buzsaki_lab_to_nwb.yuta_mossy_cell.convert_session import set_streaming_chunks


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    published_nwb_file_path: Optional[str] = None,
    include_wideband: bool = True,
    stub_test: bool = False,
):
    """Convert one session folder (a copy of GirardeauG/RatNN/RatNN-YYYYMMDD of the Buzsaki lab share).

    The rat folder (the parent of the session folder) must hold the lab's RecordingLocations.mat and sessions.mat (or
    Sessions.mat). `published_nwb_file_path` is the session's file from DANDI:000061 version 0.250624.0426, a local path
    or an S3 URL, the source of the LFP (and wide-band signal) when the session folder has no .lfp (or .dat) file.
    """
    session_path = Path(session_path)
    subject_path = session_path.parent
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            subject_folder_path=str(subject_path),
            published_nwb_file_path=str(published_nwb_file_path) if published_nwb_file_path else None,
            include_wideband=include_wideband,
        ),
        Sorting=dict(folder_path=str(session_path), subject_folder_path=str(subject_path)),
        Behavior=dict(folder_path=str(session_path)),
    )
    converter = GirardeauNWBConverter(source_data=source_data)
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
    # The videos are external files, named relative to the NWB file: link them next to it
    for series in nwbfile.acquisition.values():
        if isinstance(series, ImageSeries) and series.external_file is not None:
            for name in series.external_file:
                link_path = Path(nwbfile_path).parent / name
                if not link_path.exists():
                    os.link(session_path / name, link_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_path", type=Path, help="session folder, e.g. GirardeauG/Rat08/Rat08-20130710")
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--published", help="the session's file (path or URL) from DANDI:000061 version 0.250624.0426")
    parser.add_argument("--no-wideband", action="store_true", help="leave out the wide-band signal")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.nwbfile_path, args.published, not args.no_wideband, args.stub)
