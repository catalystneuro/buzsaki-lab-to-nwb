
class BaseDataInterface:
    
    @classmethod
    @abstractmethod
    def get_input_schema(cls):
        pass
        
    def __init__(self, **input_args):
        self.input_args = input_args

    @abstractmethod
    def get_metadata_schema(self):
        pass

    @abstractmethod
    def convert_data(self, nwbfile_path, metadata_dict):
        pass
    
class BaseRecordingExtractorInterface(BaseDataInterface):
    RecordingExtractor = None
    
    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.RX.__init__)
    
    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.recording_extactor = RecordingExtractor(**input_args)
    
    def get_metadata_schema(self):
        metadata_schema = deepcopy(base_schema)
        
        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['ElectricalSeries'] = dict(
            type='object',
            properties=[
                dict(name='name', type='string', default='ElectricalSeries'),
                dict(name='description', type='string', default='no description')
            ])
        
        return metadata_schema # RecordingExtractor metadata json-schema here.