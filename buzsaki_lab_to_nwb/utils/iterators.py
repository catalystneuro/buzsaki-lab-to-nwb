"""A chunk iterator for long multichannel signals with chunks and buffers of a fixed, sensible shape.

SliceableDataChunkIterator picks its own chunk and buffer shapes from the data's shape, and for some long recordings
(DANDI:000213 DT2-20160217, 522 million samples of 128 channels) it picks a buffer of one channel over the whole
recording. Reading such buffers from a file whose chunks hold all channels decompresses the whole file once per
channel. These shapes match set_streaming_chunks: chunks of about 32 MB of up to 16 channels, buffers of about 512 MB
across all channels.
"""

import math

import numpy as np
from neuroconv.tools.hdmf import SliceableDataChunkIterator

CHUNK_MB = 32
CHUNK_CHANNELS = 16
BUFFER_MB = 512


def signal_iterator(data, **kwargs) -> SliceableDataChunkIterator:
    """Iterate over a (samples, channels) array-like in buffers spanning all channels."""
    n_rows, n_channels = data.shape
    item_bytes = np.dtype(data.dtype).itemsize
    chunk_channels = min(n_channels, CHUNK_CHANNELS)
    chunk_rows = min(n_rows, 2 ** round(math.log2(max(1, CHUNK_MB * 1e6 / (item_bytes * chunk_channels)))))
    buffer_rows = min(n_rows, chunk_rows * max(1, int(BUFFER_MB * 1e6 // (chunk_rows * item_bytes * n_channels))))
    return SliceableDataChunkIterator(
        data=data, chunk_shape=(chunk_rows, chunk_channels), buffer_shape=(buffer_rows, n_channels), **kwargs
    )
