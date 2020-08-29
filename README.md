# buzsaki-lab-to-nwb
NWB conversion scripts and tutorials.
A collaboration with [Buzsáki Lab](https://buzsakilab.com/wp/).

# Install
```
$ pip install git+https://github.com/catalystneuro/buzsaki-lab-to-nwb
```

# Use
After activating the correct environment, the conversion function can be used in different forms:

**1. Imported and run from a python script:** <br/>
Here's an example:
```python
from datetime import datetime
from dateutil.tz import tzlocal

...
```
<br/>

**2. Command line:** <br/>
Similarly, the conversion function can be called from the command line in terminal:
```
$ ...
```
<br/>

**3. Graphical User Interface:** <br/>
To use the GUI, just run the auxiliary function `nwb_gui.py` from terminal:
```
$ python nwb_gui.py
```
![](/media/gui.PNG)
<br/>

**4. Tutorial:** <br/>
