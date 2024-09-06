"""
Very particular issue in a single session.

No available information to properly syncrhonize the trials to the rest of the file.

Simply removing the trials table, will need to be repacked (doing that anyway for pagination).
"""
import h5py

nwbfile_path = "E:/Buzsaki/PetersenP/000059/sub-MS21/sub-MS21_ses-Peter-MS21-180712-103200-concat_behavior+ecephys.nwb"

nwbfile = h5py.File(name=nwbfile_path, mode="a")

if "intervals" in nwbfile:  # remove group too since no other intervals
    if "trials" in nwbfile["intervals"]:
        del nwbfile["intervals"]["trials"]
    del nwbfile["intervals"]

nwbfile.close()
