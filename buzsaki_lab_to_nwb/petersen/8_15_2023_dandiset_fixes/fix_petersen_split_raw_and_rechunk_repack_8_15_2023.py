"""Delete bulk contents, rechunk remaining datasets, and repack all files in DANDI set 000059 with pagination."""
import h5py
from pathlib import Path
from typing import Union, Tuple, List
from warnings import warn
from uuid import uuid4

from tqdm import tqdm
from neuroconv.tools.processes import deploy_process

dandi_base = Path("E:/Buzsaki/PetersenP/000059")
all_dandi_nwbfiles = list(dandi_base.rglob("**/*.nwb"))


def recursively_rechunk_datasets(
    h5py_object: Union[h5py.Group, h5py.Dataset]
) -> List[Tuple[str, Union[Tuple[int], Tuple[int, int]]]]:
    if isinstance(h5py_object, h5py.Group):
        running_paths_and_chunk_shapes = list()
        for next_object in h5py_object.values():
            out = recursively_rechunk_datasets(h5py_object=next_object)
            if out is not None:
                running_paths_and_chunk_shapes.extend(out)
        return running_paths_and_chunk_shapes

    if isinstance(h5py_object, h5py.Dataset):
        existing_chunk_shape = h5py_object.chunks
        # if existing_chunk_shape is None:  # Not supporting forced chunking yet...
        #    return
        itemsize = h5py_object.dtype.itemsize

        location = h5py_object.name
        new_chunk_shape = None
        if existing_chunk_shape is None:  # Currently unchunked
            existing_chunk_shape = h5py_object.maxshape

        if len(existing_chunk_shape) == 1:
            new_chunk_shape = (min(10 * 1024**2 // itemsize, h5py_object.maxshape[0]),)
        elif len(existing_chunk_shape) == 2:
            # Decisions from https://github.com/flatironinstitute/neurosift/issues/52#issuecomment-1671405249
            # and https://github.com/flatironinstitute/neurosift/issues/109#issuecomment-1684481733
            # to use 64 hard bound
            max_raw_bound = min(64, h5py_object.maxshape[1])

            new_chunk_shape = (
                min(10 * 1024**2 // (itemsize * max_raw_bound), h5py_object.maxshape[0]),
                max_raw_bound,  # MANUALLY MODIFIED FOR RAW SCRIPT
            )
        elif len(existing_chunk_shape) == 3:  # Not as a general rule, but specific to this DANDI set
            new_chunk_shape = (
                min(
                    10 * 1024**2 // (itemsize * h5py_object.maxshape[1] * h5py_object.maxshape[2]),
                    h5py_object.maxshape[0],
                ),
                h5py_object.maxshape[1],
                h5py_object.maxshape[2],
            )
        elif len(existing_chunk_shape) == 0:  # mostly string 'attributes' like 'Institution'. Unsure how to handle
            pass
        else:
            warn(f"Skipping object {h5py_object} due to unsupported chunk length {existing_chunk_shape}!", stacklevel=2)

        if h5py_object.chunks is not None and h5py_object.compression is None:
            h5py_object.compression = "gzip"
            h5py_object.compression_opts = 4
        if new_chunk_shape is not None:
            return [(f'"{location}"', new_chunk_shape)]


for dandi_nwbfile in tqdm(iterable=all_dandi_nwbfiles):
    with h5py.File(name=dandi_nwbfile, mode="a") as nwbfile:
        nwbfile["identifier"][()] = str(uuid4()).encode("utf-8")
        if "intervals" in nwbfile:
            del nwbfile["intervals"]
        if "units" in nwbfile:
            del nwbfile["units"]
        if "behavior" in nwbfile["processing"]:
            del nwbfile["processing"]["behavior"]

    with h5py.File(name=dandi_nwbfile, mode="r") as nwbfile:
        paths_and_new_chunk_shapes = recursively_rechunk_datasets(h5py_object=nwbfile)

    new_dandi_nwbfile = str(dandi_nwbfile).replace("E:\\", "F:\\").replace(".nwb", "_desc-raw.nwb")
    if not Path(new_dandi_nwbfile).exists():
        # repack_command = f"h5repack -v -i {dandi_nwbfile} -o {new_dandi_nwbfile} -S PAGE -G 10485760 "
        repack_command = f"h5repack -v -i {dandi_nwbfile} -o {new_dandi_nwbfile} -S FSM_AGGR "
        for path, new_chunk_shape in paths_and_new_chunk_shapes:
            if len(new_chunk_shape) == 1:
                new_chunk_string = f"{new_chunk_shape[0]}"
            elif len(new_chunk_shape) == 2:
                new_chunk_string = f"{new_chunk_shape[0]}x{new_chunk_shape[1]}"
            elif len(new_chunk_shape) == 3:
                new_chunk_string = f"{new_chunk_shape[0]}x{new_chunk_shape[1]}x{new_chunk_shape[2]}"
            repack_command += f"-l {path}:CHUNK={new_chunk_string} -f {path}:GZIP=4 "
        output = deploy_process(command=repack_command, catch_output=True)
