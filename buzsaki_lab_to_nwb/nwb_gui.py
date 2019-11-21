# Opens the NWB conversion GUI
# authors: Luiz Tauffer and Ben Dichter
# written for Buzsaki Lab
# ------------------------------------------------------------------------------
from nwbn_conversion_tools.gui.nwbn_conversion_gui import nwbn_conversion_gui

metafile = 'metafile.yml'
conversion_module = 'conversion_module.py'

source_paths = {}
source_paths['data_1'] = {'type': 'file', 'path': ''}
source_paths['data_2'] = {'type': 'file', 'path': ''}

# Other options
kwargs = {'option_1': True, 'option_2': False}

nwbn_conversion_gui(
    metafile=metafile,
    conversion_module=conversion_module,
    source_paths=source_paths,
    kwargs_fields=kwargs,
)
