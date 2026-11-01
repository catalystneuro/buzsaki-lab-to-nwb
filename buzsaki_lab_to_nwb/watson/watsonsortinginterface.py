"""Authors: Cody Baker and Ben Dichter."""

from nwb_conversion_tools.basesortingextractorinterface import BaseSortingExtractorInterface
import spikeextractors as se
from scipy.io import loadmat
from numpy import concatenate, int64, rint


class WatsonSortingInterface(BaseSortingExtractorInterface):
    SX = se.NumpySortingExtractor

    def __init__(self, **input_args):
        self.sorting_extractor = self.SX()  # Numpy doesn't require any arguments passed

        # dislike how this is hard-coded, but it is only for a single error-prone session
        sampling_frequency = 20000
        self.sorting_extractor.set_sampling_frequency(sampling_frequency)

        spikes_mat = loadmat(input_args["spikes_file_path"])
        for j, times in enumerate(spikes_mat["spikes"]["times"][0][0][0]):
            # spikes.times in the .spikes.cellinfo.mat file are in seconds; the extractor expects frames
            frames = rint(concatenate(times) * sampling_frequency).astype(int64)
            self.sorting_extractor.add_unit(unit_id=j, times=frames)
