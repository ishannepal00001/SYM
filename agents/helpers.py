import numpy as np


def calculate_rms(chunk):
    return np.sqrt(np.mean(np.square(chunk)))
