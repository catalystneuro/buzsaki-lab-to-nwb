"""Authors: Cody Baker and Ben Dichter."""
from nwb_conversion_tools.basesortingextractorinterface import BaseSortingExtractorInterface
import spikeextractors as se
from scipy.io import loadmat
from numpy import concatenate


class WatsonSortingInterface(BaseSortingExtractorInterface):
    SX = se.NumpySortingExtractor

    def __init__(self, **input_args):
        self.sorting_extractor = self.SX()  # Numpy doesn't require any arguments passed
        
        spikes_mat = loadmat(input_args['spikes_file_path'])
        for j, times in enumerate(spikes_mat['spikes']['times'][0][0][0]):
            self.sorting_extractor.add_unit(unit_id=j, times=concatenate(times))
            # dislike how this is hard-coded, but it is only for a single error-prone session
            self.sorting_extractor.set_sampling_frequency(20000)
