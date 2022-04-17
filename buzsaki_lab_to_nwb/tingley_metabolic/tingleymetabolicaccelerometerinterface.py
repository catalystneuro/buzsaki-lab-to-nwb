"""Authors: Cody Baker."""
from nwb_conversion_tools.basedatainterface import BaseDataInterface
from nwb_conversion_tools.utils import FilePathType
from pynwb import TimeSeries, H5DataIO
from spikeextractors.extraction_tools import read_binary
from pyintan.intan import read_rhd


class TingleyMetabolicAccelerometerInterface(BaseDataInterface):
    """Aux data interface for the Tingley metabolic project."""

    def __init__(self, dat_file_path: FilePathType, rhd_file_path: FilePathType):
        """
        Process accelerometer data stored unique ad-hoc format for accelerometer data stored in an 'auxiliary.dat' file.

        The data is stored in Neuroscope .dat binary blob format, but no accompanying .xml header.
        Instead, the header is the original intan .rhd format.

        A few details to note:
        i)    Regardless of how many AUX channels are plugged in (which is read from the .rhd file), only the first 3
              have any actual data (the values for all other channels for all other time is -1).
        ii)   Even though the .rhd specifies the accelerometer data is acquired at 5kHz, the .dat has it stored at
              20kHz by duplicating the data value at every 4th index. I can only assume this was done for easier
              side-by-side analysis of the raw data (which was acquired at 20kHz).

        Parameters
        ----------
        dat_file_path : FilePathType
          DESCRIPTION.
        rhd_file_path : FilePathType
          DESCRIPTION.

        Returns
        -------
        None.

        """
        rhd_info = read_rhd(filename=rhd_file_path)
        first_aux_entry = next(
            header_info_entry
            for header_info_entry in rhd_info[1]
            if header_info_entry["native_channel_name"] == "A-AUX1"
        )
        first_aux_sub_entry = next(
            header_info_entry for header_info_entry in rhd_info[2] if header_info_entry[0] == "A-AUX1"
        )

        # Manually confirmed that all aux channels have same properties
        self.conversion = first_aux_entry["gain"]  # offset confirmed to be 0, units confirmed to be Volts
        self.sampling_frequency = first_aux_entry["sampling_rate"]
        dtype = first_aux_sub_entry[1]
        numchan = sum("AUX" in header_info_entry["native_channel_name"] for header_info_entry in rhd_info[1])

        # Manually confirmed result is still memmap after slicing
        self.memmap = read_binary(file=dat_file_path, numchan=numchan, dtype=dtype)[:3, ::4]

    def run_conversion(self, nwbfile):
        nwbfile.add_acquisition(
            TimeSeries(
                name="Accelerometer",
                description="Raw data from accelerometer sensors.",
                units="Volts",
                data=H5DataIO(self.memmap.T),  # should not need iterative write
                conversion=self.conversion,
                rate=self.sampling_frequency,
            ),
        )
