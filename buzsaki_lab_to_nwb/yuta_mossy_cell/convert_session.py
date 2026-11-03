"""Convert one Senzai and Buzsaki 2017 session (DANDI:000003) to NWB."""

import math
import re
from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.yuta_mossy_cell import SenzaiNWBConverter
from buzsaki_lab_to_nwb.yuta_mossy_cell.senzaiherd import add_external_resources

# Chunk sizes before compression, to give stored chunks of tens of MB for streaming from S3
CHUNK_MB = 32
LFP_CHUNK_CHANNELS = 16
BUFFER_MB = 512


def set_streaming_chunks(backend_configuration):
    """Chunk every dataset along its first axis to about CHUNK_MB, or keep it in one chunk if it is smaller.

    The LFP and wide-band signals are also split into groups of LFP_CHUNK_CHANNELS channels.
    """
    for location, configuration in backend_configuration.dataset_configurations.items():
        full_shape = configuration.full_shape
        if not full_shape or 0 in full_shape:
            continue
        item_bytes = configuration.dtype.itemsize
        if location.endswith(("LFP/lfp/data", "acquisition/ElectricalSeries/data")):
            other_axes = (min(full_shape[1], LFP_CHUNK_CHANNELS),)
        else:
            other_axes = full_shape[1:]
        bytes_per_row = item_bytes * math.prod(other_axes)
        if full_shape[0] * bytes_per_row <= CHUNK_MB * 1e6:
            rows = full_shape[0]
        else:
            rows = min(full_shape[0], 2 ** round(math.log2(CHUNK_MB * 1e6 / bytes_per_row)))
        buffer_rows = rows * max(1, int(BUFFER_MB * 1e6 // (rows * item_bytes * math.prod(full_shape[1:]))))
        backend_configuration.dataset_configurations[location] = configuration.model_copy(
            update=dict(
                chunk_shape=(rows, *other_axes), buffer_shape=(min(full_shape[0], buffer_rows), *full_shape[1:])
            )
        )


def session_to_nwb(
    session_path: Path,
    project_path: Path,
    nwbfile_path: Path,
    published_nwb_file_path: Optional[Path] = None,
    stub_test: bool = False,
):
    """Convert one session folder.

    `project_path` holds the lab's DG_all_6__UnitFeatureSummary_add.mat and YM## exp_sheet.xlsx files.
    `published_nwb_file_path` is the session's file from an earlier version of DANDI:000003, the source of the LFP,
    wide-band signal, auxiliary inputs and spike waveforms.
    """
    session_path, project_path = Path(session_path), Path(project_path)
    session_id = session_path.name
    published = str(published_nwb_file_path) if published_nwb_file_path else None

    hilus_channels = {
        int(re.search(r"\.ch(\d+)\.evt$", path.name).group(1))
        for path in session_path.glob(f"{session_id}.DS2.ch*.evt")
    }
    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            published_nwb_file_path=published,
            hilus_channel=hilus_channels.pop() if len(hilus_channels) == 1 else None,
        ),
        Sorting=dict(
            folder_path=str(session_path),
            unit_summary_file_path=str(project_path / "DG_all_6__UnitFeatureSummary_add.mat"),
            published_nwb_file_path=published,
        ),
        Behavior=dict(folder_path=str(session_path)),
    )
    monosynaptic_file_path = session_path / f"{session_id}-MonoSynConvClick.mat"
    if monosynaptic_file_path.is_file():
        source_data.update(Monosynaptic=dict(file_path=str(monosynaptic_file_path)))

    converter = SenzaiNWBConverter(source_data=source_data, exp_sheet_folder_path=project_path)
    shank_sizes = {len(channels) for channels in converter.data_interface_objects["Ecephys"].xml_info["shank_channels"]}
    converter.data_interface_objects["Ecephys"].source_data["probe"] = (
        "Buzsaki64sp" if 10 in shank_sizes else "Buzsaki64"
    )

    metadata = dict_deep_update(converter.get_metadata(), load_dict_from_file(Path(__file__).parent / "metadata.yml"))
    conversion_options = dict(Ecephys=dict(stub_test=stub_test), Sorting=dict(stub_test=stub_test))
    nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
    add_external_resources(nwbfile)
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    set_streaming_chunks(backend_configuration)
    configure_and_write_nwbfile(
        nwbfile=nwbfile, nwbfile_path=str(nwbfile_path), backend_configuration=backend_configuration
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_path", type=Path, help="session folder, e.g. SenzaiY/YutaMouse41/YutaMouse41-150829")
    parser.add_argument("project_path", type=Path, help="folder with the unit summary and experiment sheets")
    parser.add_argument("nwbfile_path", type=Path)
    parser.add_argument("--published", type=Path, help="the session's file from DANDI:000003 version 0.260218.2052")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    session_to_nwb(args.session_path, args.project_path, args.nwbfile_path, args.published, args.stub)
