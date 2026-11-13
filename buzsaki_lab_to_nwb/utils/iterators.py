"""Chunk and buffer shapes for streaming the Buzsaki lab files from S3, and a chunk iterator that follows them.

Chunks are a middle ground between the two common ways of reading a multichannel signal: a short window of all
channels, and a few channels over a long stretch. Each chunk holds at most CHUNK_CHANNELS channels and a few seconds
of the wide-band signal (WIDEBAND_SAMPLES, 8.7 s at 30 kHz) or about a minute of LFP (LFP_SAMPLES, 52 s at
1250 Hz): 2 to 8 MB before compression for int16 data. With 64 channels, a 1 s window of all channels then fetches
4 chunks, and one channel over the whole recording fetches 16 times its data. Other datasets are chunked along their
first axis to about OTHER_CHUNK_MB, so that no table or series is one large chunk.

SliceableDataChunkIterator picks its own buffer shape from the data's shape, and for some long recordings it picks
one channel over the whole recording (DANDI:000213 DT2-20160217, 522 million samples of 128 channels; DANDI:000552
e13_26m1_211116, 618,657,540 x 128). Writing such buffers into chunks of 16 channels reads back and rewrites every
compressed chunk once per channel. The buffers here span all channels and whole chunks (about BUFFER_MB).
"""

import math
import re

import numpy as np
from neuroconv.tools.hdmf import SliceableDataChunkIterator

CHUNK_CHANNELS = 16
WIDEBAND_SAMPLES = 2**18
LFP_SAMPLES = 2**16
OTHER_CHUNK_MB = 8
BUFFER_MB = 512

# A multichannel signal: the data of an acquisition series, or of a series in the ecephys processing module
SIGNAL = re.compile(r"^(acquisition/[^/]+|processing/ecephys/(.+/)?[^/]+)/data$")


def signal_kind(location: str, shape: tuple, dtype) -> str | None:
    """'lfp' or 'wideband' for a 2-D integer signal of several channels, None for anything else."""
    if len(shape) != 2 or shape[1] < 2 or not np.issubdtype(np.dtype(dtype), np.integer) or not SIGNAL.match(location):
        return None
    return "lfp" if "lfp" in location.lower() else "wideband"


def chunk_rows(n_rows: int, kind: str) -> int:
    return min(n_rows, LFP_SAMPLES if kind == "lfp" else WIDEBAND_SAMPLES)


def buffer_rows(n_rows: int, n_channels: int, item_bytes: int) -> int:
    """Whole multiples of WIDEBAND_SAMPLES (and so of LFP_SAMPLES) across all channels, about BUFFER_MB."""
    step = min(n_rows, WIDEBAND_SAMPLES)
    return min(n_rows, step * max(1, int(BUFFER_MB * 1e6 // (step * item_bytes * n_channels))))


def set_streaming_chunks(backend_configuration):
    """Set the chunk and buffer shape of every dataset of a NeuroConv backend configuration (see the module notes)."""
    for location, configuration in backend_configuration.dataset_configurations.items():
        full_shape = configuration.full_shape
        if not full_shape or 0 in full_shape:
            continue
        item_bytes = configuration.dtype.itemsize
        kind = signal_kind(location, full_shape, configuration.dtype)
        if kind is not None:
            chunk = (chunk_rows(full_shape[0], kind), min(full_shape[1], CHUNK_CHANNELS))
            buffer = (buffer_rows(full_shape[0], full_shape[1], item_bytes), full_shape[1])
        else:
            bytes_per_row = item_bytes * math.prod(full_shape[1:])
            if full_shape[0] * bytes_per_row <= OTHER_CHUNK_MB * 1e6:
                rows = full_shape[0]
            else:
                rows = min(full_shape[0], 2 ** max(0, round(math.log2(OTHER_CHUNK_MB * 1e6 / bytes_per_row))))
            chunk = (rows, *full_shape[1:])
            buffer = (
                min(full_shape[0], rows * max(1, int(BUFFER_MB * 1e6 // (rows * bytes_per_row)))),
                *full_shape[1:],
            )
        backend_configuration.dataset_configurations[location] = configuration.model_copy(
            update=dict(chunk_shape=chunk, buffer_shape=buffer)
        )


def signal_iterator(data, kind: str = "wideband", **kwargs) -> SliceableDataChunkIterator:
    """Iterate over a (samples, channels) array-like in buffers of whole chunks spanning all channels."""
    n_rows, n_channels = data.shape
    item_bytes = np.dtype(data.dtype).itemsize
    return SliceableDataChunkIterator(
        data=data,
        chunk_shape=(chunk_rows(n_rows, kind), min(n_channels, CHUNK_CHANNELS)),
        buffer_shape=(buffer_rows(n_rows, n_channels, item_bytes), n_channels),
        **kwargs,
    )
