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
These datasets can sometimes be multiple TB in total size, so direct download to local devices for conversionions is not recommended.
Instead, we'll use a remote server for full runs of scripts developed and tested locally - more on that in the final steps.

For local debugging, it is recommended to download one random session from each subject of the dataset.

For example, the `PetersenP` dataset has subject subfolders `MS{x}` for `x = [10, 12, 13, 14, 21, 22]`.

Each of these contains multiple sessions for each subject, of the form `Peter_MS{x}_%y%m%d_%h%m%s` where the remaing details are datetime strings of the start time for each session. There may also be additional strings appended to the session name.

For prototyping, we would download a randomly chosen session for each subject. If none of these contain any raw data, I would reccomend specifically finding a session that does contain some so that it is included in the prototyping stage.


## Build converter class
From `nwb-conversion-tools`, construct an NWBConverter class that covers as many of the data types available in the dataset. For example,
```
class PetersenNWBConverter(NWBConverter):
    """Primary conversion class for the PetersenP dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=PetersenNeuroscopeRecordingInterface,
        PhySorting=PhySortingInterface,
        CellExplorer=CellExplorerSortingInterface,
        NeuroscopeLFP=PetersenNeuroscopeLFPInterface,
    )
  ```
 we will add in more interfaces later as we develop them custom to each experiment.
  
## Build conversion script
Construct a script that instantiates the converter object as well as specifies any other dataset metadata that applies to each session. It is recommended to apply paralleziation at this stage as well. This will be the primary way you end up running the conversion in the final steps.
 
These can honestly just be copied & pasted from previous conversions, such as https://github.com/catalystneuro/buzsaki-lab-to-nwb/blob/add_petersen/buzsaki_lab_to_nwb/petersen_code/convert_petersen.py

Be sure to keep `stub_test=True` as a conversion option throughout this step in order to debug as quickly as possible.
 
## Build specialized data interfaces for new data
This is where most time will be spent; designing a `DataInterface` class, in particular the `run_conversion()` method, for data not covered by those inherited from nwb-conversion-tools. This most often includes behavioral data such as trial events, states, and position tracking. Further, previous datasets rarely tend to use the same exact method of storing these data, so I/O has to be developed from scratch for each new file.
