"""Authors: Heberto Mayorquin and Cody Baker."""
from mat73 import loadmat as loadmat_mat73
from mat4py import loadmat as loadmat_mat4py
from scipy.io import loadmat as loadmat_scipy


def read_matlab_file(file_path):
    file_path = str(file_path)

    try:
        mat_file = loadmat_mat4py(str(file_path))
    except:
        try:
            mat_file = loadmat_mat73(file_path)
        except:
            mat_file = loadmat_scipy(file_path)
    return mat_file
