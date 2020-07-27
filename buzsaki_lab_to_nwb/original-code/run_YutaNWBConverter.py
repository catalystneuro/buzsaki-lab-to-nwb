
input_file_schema = BuzsakiLabNWBConverter.get_input_schema()

# construct input_args dict according to input schema, e.g.: 
input_args = {'intan': {'fpath': "my_intan_path"},
              'bpod': {'fpath':'my_bpod_path'}}

blab_converter = BuccinoLabNWBConverter(**input_args)

expt_json_schema = blab_converter.get_metadata_schema()

# construct metadata_dict according to expt_json_schema, e.g. 
metadata_dict = {
    'intan': {
        'ElectricalSeries': {
            'name': 'ElectricalSeries',
            'description': 'no description'
        }
    },
    'bpod': {
        'SpatialSeries': {
            'name': 'leg_position',
            'description': 'position tracked by XXX'
        }
    }
}

nwbfile_path = 'nwb_out.nwb'
blab_converter.run_conversion(nwbfile_path, metadata_dict)