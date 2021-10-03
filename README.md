# buzsaki-lab-to-nwb
NWB conversion scripts for popular datasets.
A collaboration with [Buzsáki Lab](https://buzsakilab.com/wp/).

# Clone and dev install
```
$ git clone https://github.com/catalystneuro/buzsaki-lab-to-nwb
$ pip install -e buzsaki-lab-to-nwb
```

# Workflow
Here is a basic description of the standard conversion pipeline for this project.

## Download local data
These datasets can sometimes be multiple TB in total size, so direct download to local devices for conversions is not recommended.
Instead, we'll use a remote server for full runs of scripts developed and tested locally - more on that in the final steps.

For local debugging, it is recommended to download one random session from each subject of the dataset. You can find the globus endpoint here: https://buzsakilab.com/wp/ -> Databank -> Globus Datasets.

For example, the `PetersenP` dataset has subject subfolders `MS{x}` for `x = [10, 12, 13, 14, 21, 22]`.

Each of these contains multiple sessions for each subject, of the form `Peter_MS{x}_%y%m%d_%h%m%s` where the remaing details are datetime strings of the start time for each session. There may also be additional strings appended to the session name.

For prototyping, we would download a randomly chosen session for each subject. If none of these contain any raw data (`.dat` files), I would recommend specifically finding a session that does contain some so that it is included in the prototyping stage.

In some cases, there may be more subjects or sessions included in the globus dataset than were used in the corresponding publication; start confirming this by going through the methods or supplementary section of the corresponding paper to see if those details are included. If not, send an email to the corresponding author to obtain a list of sessions used for final analysis. A good example of this in the PetersenP dataset is that `MS14` was not actually used in the publication even though there is data available for it; thus, we will skip this mouse when converting the dataset.


## Build converter class
From `nwb-conversion-tools`, construct an NWBConverter class that covers as many of the data types available in the dataset. For example,
```
class PetersenNWBConverter(NWBConverter):
    """Primary conversion class for the PetersenP dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=PetersenNeuroscopeRecordingInterface,
        NeuroscopeLFP=PetersenNeuroscopeLFPInterface,
        PhySorting=PhySortingInterface,
    )
  ```
 We will add more interfaces later as we develop them custom to each experiment.
  
## Build conversion script
Construct a script that instantiates the converter object as well as specifies any other dataset metadata that applies to each session. It is recommended to apply paralleziation at this stage as well. This will be the primary way you end up running the conversion in the final steps.
 
These can honestly just be copied & pasted from previous conversions, such as https://github.com/catalystneuro/buzsaki-lab-to-nwb/blob/add_petersen/buzsaki_lab_to_nwb/petersen_code/convert_petersen.py, with all dataset specific naming and descriptions updated to correspond to this particular conversion.

Be sure to keep `stub_test=True` as a conversion option throughout this step in order to debug as quickly as possible.
 
## Build specialized data interfaces for new data
This is where most time will be spent; designing a `DataInterface` class, in particular the `run_conversion()` method, for data not covered by those inherited from `nwb-conversion-tools`. This most often includes behavioral data such as trial events, states, and position tracking. Further, previous datasets rarely tend to use the same exact method of storing these data so I/O has to be developed from scratch for each new file.

## Remote server
Now it's time to download all the available data from the endpoint onto the remote server for conversion. It's critical this data go onto the mounted drive of `/mnt/scrap/catalystneuro`.

When download is complete, try to run the full conversion with `stub_test` still set to `True`. Occasionally certain bugs only show up during this stage as they may correspond only to a handful of sessions in the dataset.

When all tests are passing with `stub_test=True`, investigate some of the NWB files with widgets or other viewers to ensure everything looks OK. Post some on the slack as well so Ben and Cody can approve.

Once approved, set `stub_test=False` and begin the full conversion with parallelization options set to maximum of 12 cores and ?? (I need to check) RAM buffer per job.

After it is complete, double check the NWB files with widgets to make sure the full conversion went as expected; if everything looks good, create a new DANDI set, fill in requisite metadata, and proceed with upload to the archive.
