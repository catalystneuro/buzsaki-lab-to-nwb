# This script converts data to .nwb files.
# authors: Luiz Tauffer and Ben Dichter
# written for Buzsaki Lab
# ------------------------------------------------------------------------------
from pynwb import NWBFile, NWBHDF5IO, ProcessingModule

import matplotlib.pyplot as plt
import yaml
import numpy as np
import os


def conversion_function(source_paths, f_nwb, metafile, **kwargs):
    """
    Converts data to a single NWB file.

    Parameters
    ----------
    source_paths : dict
        Dictionary with paths to source files/directories. e.g.:
    f_nwb : str
        Path to output NWB file, e.g. 'my_file.nwb'.
    metafile : str
        Path to .yml meta data file
    **kwargs : key, value pairs
        Extra keyword arguments
    """

    # Load meta data from YAML file
    with open(metafile) as f:
        meta = yaml.safe_load(f)

    # Initialize a NWB object
    nwb = NWBFile(**meta['NWBFile'])

    # Create and add device
    device = Device(**meta['Ophys']['Device'])
    nwb.add_device(device)

    # Saves to NWB file
    with NWBHDF5IO(f_nwb, mode='w') as io:
        io.write(nwb)
    print('NWB file saved with size: ', os.stat(f_nwb).st_size/1e6, ' mb')


# If called directly fom terminal
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 6:
        print('Error: Please provide source files, nwb file name and metafile.')

    f1 = sys.argv[1]
    f2 = sys.argv[2]
    f3 = sys.argv[3]
    source_paths = {
        'processed data': {'type': 'file', 'path': f1},
        'sparse matrix': {'type': 'file', 'path': f2},
        'ref image': {'type': 'file', 'path': f3}
    }
    f_nwb = sys.argv[4]
    metafile = sys.argv[5]
    plot_rois = False
    conversion_function(source_paths=source_paths,
                        f_nwb=f_nwb,
                        metafile=metafile,
                        plot_rois=plot_rois)
