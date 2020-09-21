# This script converts data to .nwb files.
# authors: Luiz Tauffer and Ben Dichter
# written for Buzsaki Lab
# ------------------------------------------------------------------------------
from nwb_conversion_tools.ecephys.neuroscope import Neuroscope2NWB
from pathlib import Path
import yaml


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
        metadata = yaml.safe_load(f)

    # Prepare paths for Neuroscope converter
    source_paths = {}

    # Instantiate a Neuroscope converter
    converter = Neuroscope2NWB(
        metadata=metadata,
        source_paths=source_paths
    )

    # TODO ---------------------------------
    raise NotImplementedError('TODO')
    # --------------------------------------

    # Saves to NWB file
    converter.save(
        to_path=Path.cwd(),
        read_check=True
    )


# If called directly fom terminal
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 6:
        print('Error: Please provide source files, nwb file name and metafile.')

    f1 = sys.argv[1]
    f2 = sys.argv[2]
    f3 = sys.argv[3]
    source_paths = {
        'paths1': {'type': 'file', 'path': f1},
        'paths2': {'type': 'file', 'path': f2},
        'paths3': {'type': 'file', 'path': f3}
    }
    f_nwb = sys.argv[4]
    metafile = sys.argv[5]

    conversion_function(
        source_paths=source_paths,
        f_nwb=f_nwb,
        metafile=metafile,
    )
