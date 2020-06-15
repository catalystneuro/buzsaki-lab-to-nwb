#from datetime import datetime#

from pynwb import NWBFile

from functools import partialmethod, partial
from copy import deepcopy


#MockNWBFile = deepcopy(NWBFile)
#MockNWBFile.__init__ = partialmethod(NWBFile.__init__,
#                                     source='source',
#                                     session_description='session_description',
#                                     identifier='identifier',
#                                     session_start_time=datetime.now(),
#                                     file_create_date=datetime.now(),
#                                     institution='institution',
#                                     lab='lab')

#mock_nwb_file = MockNWBFile()

#MockProcessingModule = partial(MockNWBFile().create_processing_module,
#                               name='name', source='source',
#                               description='description')



#mock_processing_module = mock_nwb_file.create_processing_module()

