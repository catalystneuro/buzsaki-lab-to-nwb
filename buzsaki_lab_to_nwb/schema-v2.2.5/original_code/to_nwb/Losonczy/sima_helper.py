import os
import pickle
import sima

import numpy as np

from pynwb import TimeSeries


def get_motion_correction(expt, channel):
    fpath = os.path.join(expt.sima_path(), 'sequences.pkl')

    with open(fpath, 'rb') as f:
        aa = pickle.load(f)

    obj = aa[0]

    while True:
        if 'displacements' in obj:
            data = np.swapaxes(obj['displacements'][..., channel], 1, 2)
            return TimeSeries(name='motion_correction', data=data, unit='pixels', rate=1 / expt.frame_period())
        obj = obj['base']
