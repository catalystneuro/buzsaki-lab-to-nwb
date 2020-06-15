from collections import Iterable

from pynwb import load_namespaces, register_class, TimeSeries, register_map
from pynwb.core import NWBDataInterface
from hdmf.utils import docval, getargs, popargs, fmt_docval_args
from hdmf.data_utils import AbstractDataChunkIterator, DataIO
from hdmf.build import ObjectMapper

# load custom classes
name = 'general'
ns_path = name + '.namespace.yaml'
ext_source = name + '.extensions.yaml'
load_namespaces(ns_path)


@register_class('CatCellInfo', name)
class CatCellInfo(NWBDataInterface):
    __nwbfields__ = ('values', 'indices', 'cell_index')

    @docval({'name': 'name', 'type': str, 'doc': 'name'},
            {'name': 'values', 'type': Iterable, 'doc': 'unique values as strings'},
            {'name': 'indices', 'type': Iterable, 'doc': 'indexes into those values'},
            {'name': 'cell_index', 'type': Iterable,  'default': None,
             'doc': 'global id for neuron'})
    def __init__(self, **kwargs):
        name, values, indices, cell_index = popargs(
            'name', 'values', 'indices', 'cell_index', kwargs)
        super(CatCellInfo, self).__init__(name, **kwargs)

        self.values = values
        self.indices = indices
        if cell_index is not None:
            self.cell_index = cell_index


@register_class('CatTimeSeries', name)
class CatTimeSeries(TimeSeries):
    __nwbfields__ = ("comments",
                     "description",
                     "data",
                     "num_samples",
                     "timestamps",
                     "timestamps_unit",
                     "interval",
                     "starting_time",
                     "rate",
                     "rate_unit",
                     "control",
                     "control_description",
                     "values")

    __time_unit = "Seconds"

    @docval({'name': 'name', 'type': str, 'doc': 'The name of this CatTimeSeries dataset'},
            {'name': 'data', 'type': ('array_data', 'data', 'TimeSeries'),
             'doc': 'The data this TimeSeries dataset stores. Can also store binary data e.g. image frames',
             'default': None},
            {'name': 'values', 'type': ('array_data', 'data'), 'doc': 'Categories of data'},
            # Optional arguments:
            {'name': 'timestamps', 'type': ('array_data', 'data', 'TimeSeries'),
             'doc': 'Timestamps for samples stored in data', 'default': None},
            {'name': 'starting_time', 'type': float, 'doc': 'The timestamp of the first sample', 'default': None},
            {'name': 'rate', 'type': float, 'doc': 'Sampling rate in Hz', 'default': None},
            {'name': 'comments', 'type': str,
             'doc': 'Human-readable comments about this TimeSeries dataset', 'default': 'no comments'},
            {'name': 'description', 'type': str,
             'doc': 'Description of this TimeSeries dataset', 'default': 'no description'},
            {'name': 'control', 'type': Iterable,
             'doc': 'Numerical labels that apply to each element in data', 'default': None},
            {'name': 'control_description', 'type': Iterable,
             'doc': 'Description of each control value', 'default': None},
            {'name': 'parent', 'type': 'NWBContainer',
             'doc': 'The parent NWBContainer for this NWBContainer', 'default': None})
    def __init__(self, **kwargs):
        """Create a TimeSeries object
        """
        pargs, pkwargs = fmt_docval_args(super(TimeSeries, self).__init__, kwargs)
        super(TimeSeries, self).__init__(*pargs, **pkwargs)
        keys = ("comments",
                "description",
                "conversion",
                "control",
                "control_description")
        for key in keys:
            val = kwargs.get(key)
            if val is not None:
                setattr(self, key, val)
        data = getargs('data', kwargs)
        self.fields['data'] = data
        if isinstance(data, TimeSeries):
            data.__add_link('data_link', self)
            self.fields['num_samples'] = data.num_samples
        elif isinstance(data, AbstractDataChunkIterator):
            self.fields['num_samples'] = -1
        elif isinstance(data, DataIO):
            this_data = data.data
            if isinstance(this_data, AbstractDataChunkIterator):
                self.fields['num_samples'] = -1
            else:
                self.fields['num_samples'] = len(this_data)
        elif data is None:
            self.fields['num_samples'] = 0
        else:
            self.fields['num_samples'] = len(data)

        timestamps = kwargs.get('timestamps')
        starting_time = kwargs.get('starting_time')
        rate = kwargs.get('rate')
        if timestamps is not None:
            self.fields['timestamps'] = timestamps
            self.timestamps_unit = 'Seconds'
            self.interval = 1
            if isinstance(timestamps, TimeSeries):
                timestamps.__add_link('timestamp_link', self)
        elif rate is not None:
            self.rate = rate
            self.rate_unit = 'Seconds'
            if starting_time is not None:
                self.starting_time = starting_time
            else:
                self.starting_time = 0.0
        else:
            raise TypeError("either 'timestamps' or 'rate' must be specified")


@register_map(CatTimeSeries)
class CatTimeSeriesMap(ObjectMapper):

    def __init__(self, spec):
        super(CatTimeSeriesMap, self).__init__(spec)
        data_spec = self.spec.get_dataset('data')
        timestamps_spec = self.spec.get_dataset('timestamps')
        self.map_attr('timestamps_unit', timestamps_spec.get_attribute('unit'))
        # self.map_attr('interval', timestamps_spec.get_attribute('interval'))
        startingtime_spec = self.spec.get_dataset('starting_time')
        self.map_attr('values', data_spec.get_attribute('values'))
        self.map_attr('rate_unit', startingtime_spec.get_attribute('unit'))
        self.map_attr('rate', startingtime_spec.get_attribute('rate'))

    @ObjectMapper.constructor_arg('name')
    def name(self, builder, manager):
        return builder.name
