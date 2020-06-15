import os

from h5py import File
from tqdm import tqdm
from datetime import datetime
import numpy as np

from pynwb import NWBFile, NWBHDF5IO
from pynwb.behavior import SpatialSeries, Position

from to_nwb.utils import check_module

import sys


def read_ragged_array(struct, i=None, gid=None):
    """Read item x from ragged array STRUCT

    Parameters
    ----------
    struct: h5py.Group
    gid: int (optional)
    i: int (optional)

    Returns
    -------

    np.array

    """
    if i is not None and gid is not None:
        raise ValueError('only i or gid can be supplied')
    if i is None and gid is None:
        return np.array([read_ragged_array(struct, i)
                         for i in tqdm(struct['Cell Index'][:])])
    if gid:
        if 'Cell Index' in struct:
            i = np.argmax(struct['Cell Index'][:] == gid)[0]
        else:
            i = gid

    i = int(i)

    start = struct['Attribute Pointer'][i]
    stop = struct['Attribute Pointer'][i+1]

    return struct['Attribute Value'][start:stop].astype(float)


def get_neuroh5_cell_data(f):
    """

    Parameters
    ----------
    f: h5py.File

    Yields
    -------
    dict

    """
    labs = f['H5Types']['Population labels']
    population_table = f['H5Types']['Populations']
    cell_types_order = {labs.id.get_member_value(i): labs.id.get_member_name(i)
                        for i in range(labs.id.get_nmembers())}
    start_dict = {pop_name.decode(): population_table['Start'][population_table['Population'] == pop_int][0]
                  for pop_int, pop_name in cell_types_order.items()}

    pops = f['Populations']
    for cell_type in pops:
        spike_struct = pops[cell_type]['Vector Stimulus 100']['spiketrain']
        for pop_id in spike_struct['Cell Index']:
            spike_times = read_ragged_array(spike_struct, pop_id) / 1000
            gid = pop_id + start_dict[cell_type]
            yield {'id': int(gid), 'pop_id': int(pop_id), 'spike_times': spike_times, 'cell_type': cell_type}


def write_position(nwbfile, f, name='Trajectory 100'):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
    f: h5py.File
    name: str (optional)

    Returns
    -------
    pynwb.core.ProcessingModule

    """
    obj = f[name]
    behavior_mod = check_module(nwbfile, 'behavior')

    spatial_series = SpatialSeries('Position', data=np.array([obj['x'], obj['y']]).T,
                                   reference_frame='NA',
                                   conversion=1 / 100.,
                                   resolution=np.nan,
                                   rate=float(1 / np.diff(obj['t'][:2]) * 1000))

    behavior_mod.add_data_interface(Position(spatial_series))

    return behavior_mod


def neuroh5_to_nwb(fpath, out_path=None):
    """

    Parameters
    ----------
    fpath: str | path
        path of neuroh5 file
    out_path: str (optional)
        where the NWB file is saved

    """

    if out_path is None:
        out_path = fpath[:-3] + '.nwb'

    fname = os.path.split(fpath)[1]
    identifier = fname[:-4]

    nwbfile = NWBFile(session_description='session_description',
                      identifier=identifier,
                      session_start_time=datetime.now().astimezone(),
                      institution='Stanford University', lab='Soltesz')

    with File(fpath, 'r') as f:
        write_position(nwbfile, f)

        nwbfile.add_unit_column('cell_type', 'cell type')
        nwbfile.add_unit_column('pop_id', 'cell number within population')

        for unit_dict in tqdm(get_neuroh5_cell_data(f),
                              total=38000+34000,
                              desc='reading cell data'):
            nwbfile.add_unit(**unit_dict)

    with NWBHDF5IO(out_path, 'w') as io:
        io.write(nwbfile)


def main(argv):
    neuroh5_to_nwb('/Users/bendichter/Desktop/Soltesz/data/DG_PP_spiketrain_12142018.h5')


if __name__ == "__main__":
    main(sys.argv[1:])
