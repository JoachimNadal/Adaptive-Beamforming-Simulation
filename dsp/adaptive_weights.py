import numpy as np

def lms_update(weights, input_vector, error, mu):
    """
    Perform one LMS weight update.

    Parameters
    ----------
    weights : np.ndarray
        Current complex weight vector.

    input_vector : np.ndarray
        Current received signal vector.

    error : complex
        Error between desired signal and beamformer output.

    mu : float
        LMS learning rate.

    Returns
    -------
    np.ndarray
        Updated weight vector.
    """

    return weights + mu * input_vector * np.conjugate(error)
