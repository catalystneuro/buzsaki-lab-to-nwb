"""Convert one Watson et al. 2016 session (DANDI:000041) to NWB."""

import math
from pathlib import Path
from typing import Optional

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_default_backend_configuration
from neuroconv.utils import dict_deep_update, load_dict_from_file

from buzsaki_lab_to_nwb.watson import WatsonNWBConverter

# All sessions in DANDI:000041
SESSIONS = [
    "BWRat17/BWRat17_121712",
    "BWRat17/BWRat17_121912",
    "BWRat18/BWRat18_020513",
    "BWRat19/BWRat19_032413",
    "BWRat19/BWRat19_032513",
    "BWRat20/BWRat20_101013",
    "BWRat20/BWRat20_101513",
    "BWRat21/BWRat21_121113",
    "BWRat21/BWRat21_121613",
    "BWRat21/BWRat21_121813",
    "Bogey/Bogey_012615",
    "Dino/Dino_061814",
    "Dino/Dino_061914",
    "Dino/Dino_062014",
    "Dino/Dino_072114",
    "Dino/Dino_072314",
    "Dino/Dino_072414",
    "Rizzo/Rizzo_022615",
    "Rizzo/Rizzo_022715",
    "Splinter/Splinter_020515",
    "Splinter/Splinter_020915",
    "Templeton/Templeton_032415",
]

# Published LFP that cannot be reused. Dino_061914's was reshaped to 125 columns from a file whose size is not a
# multiple of its 128 channels, so its columns do not correspond to channels.
UNUSABLE_PUBLISHED_LFP = {"Dino/Dino_061914"}

# Chunk sizes before compression. gzip shrinks the LFP and the phases by less than 25% and the spike waveforms by
# about 3x, so these give stored chunks of roughly 20-35 MB: large enough that streaming from S3 is not dominated by
# the overhead of each range request, small enough that a short read does not fetch much more than it needs.
CHUNK_MB = 32
WAVEFORM_CHUNK_MB = 64
LFP_CHUNK_CHANNELS = 16
BUFFER_MB = 512


def set_streaming_chunks(backend_configuration):
    """Chunk every dataset along time (its first axis) to about CHUNK_MB, or keep it in one chunk if it is smaller.

    The LFP is also split into groups of LFP_CHUNK_CHANNELS channels, so that reading one channel does not fetch
    them all. Spike waveforms are never split across channels or samples.
    """
    for location, configuration in backend_configuration.dataset_configurations.items():
        full_shape = configuration.full_shape
        if not full_shape or 0 in full_shape:
            continue
        item_bytes = configuration.dtype.itemsize
        if location.endswith("LFP/lfp/data"):
            other_axes = (min(full_shape[1], LFP_CHUNK_CHANNELS),)
            buffer_other_axes = full_shape[1:]
        else:
            other_axes = buffer_other_axes = full_shape[1:]
        chunk_mb = WAVEFORM_CHUNK_MB if "SpikeWaveforms" in location else CHUNK_MB
        bytes_per_row = item_bytes * math.prod(other_axes)
        if full_shape[0] * bytes_per_row <= chunk_mb * 1e6:
            rows = full_shape[0]
        else:
            rows = min(full_shape[0], 2 ** round(math.log2(chunk_mb * 1e6 / bytes_per_row)))
        buffer_rows = rows * max(1, int(BUFFER_MB * 1e6 // (rows * item_bytes * math.prod(buffer_other_axes))))
        backend_configuration.dataset_configurations[location] = configuration.model_copy(
            update=dict(
                chunk_shape=(rows, *other_axes),
                buffer_shape=(min(full_shape[0], buffer_rows), *buffer_other_axes),
            )
        )


def session_to_nwb(
    session_path: Path,
    nwbfile_path: Path,
    published_nwb_file_path: Optional[Path] = None,
    stub_test: bool = False,
):
    """Convert one session folder.

    The LFP is read from the session's .lfp file, or else from `published_nwb_file_path`, the session's file from
    an earlier version of DANDI:000041. Without either, the file has no LFP or LFP phase decompositions.
    """
    session_path = Path(session_path)
    session_id = session_path.name
    lfp_file_path = session_path / f"{session_id}.lfp"

    source_data = dict(
        Ecephys=dict(
            folder_path=str(session_path),
            lfp_file_path=str(lfp_file_path) if lfp_file_path.is_file() else None,
            published_nwb_file_path=str(published_nwb_file_path) if published_nwb_file_path else None,
        ),
        Sorting=dict(folder_path=str(session_path)),
    )
    sleep_state_file_path = session_path / f"{session_id}.SleepState.states.mat"
    if sleep_state_file_path.is_file():
        source_data.update(SleepStates=dict(file_path=str(sleep_state_file_path)))

    converter = WatsonNWBConverter(source_data=source_data)
    metadata = dict_deep_update(converter.get_metadata(), load_dict_from_file(Path(__file__).parent / "metadata.yml"))
    conversion_options = dict(Ecephys=dict(stub_test=stub_test), Sorting=dict(stub_test=stub_test))
    nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    set_streaming_chunks(backend_configuration)
    configure_and_write_nwbfile(
        nwbfile=nwbfile, nwbfile_path=str(nwbfile_path), backend_configuration=backend_configuration
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_path", type=Path, help="folder holding the WatsonBO subject folders")
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--published-path", type=Path, help="folder with the DANDI:000041 sub-* folders")
    parser.add_argument("--session", action="append", help="e.g. BWRat17/BWRat17_121912; default: all sessions")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()

    args.output_path.mkdir(parents=True, exist_ok=True)
    failed = {}
    for session in args.session or SESSIONS:
        subject_id, session_id = session.split("/")
        published_nwb_file_path = None
        if args.published_path and session not in UNUSABLE_PUBLISHED_LFP:
            dandi_session = session_id.replace("_", "-")
            candidate = args.published_path / f"sub-{subject_id}" / f"sub-{subject_id}_ses-{dandi_session}_ecephys.nwb"
            published_nwb_file_path = candidate if candidate.is_file() else None
        print(f"Converting {session}")
        try:
            session_to_nwb(
                session_path=args.base_path / session,
                nwbfile_path=args.output_path / f"{session_id}{'_stub' if args.stub else ''}.nwb",
                published_nwb_file_path=published_nwb_file_path,
                stub_test=args.stub,
            )
        except Exception as error:
            failed[session] = repr(error)
            print(f"Failed: {error!r}")
    for session, error in failed.items():
        print(f"{session}: {error}")
