import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from simulations.antenna_array.linear_array import LinearArray


@pytest.fixture
def ula4():
    return LinearArray(num_elements=4, spacing=6.25)


@pytest.fixture
def ula8():
    return LinearArray(num_elements=8, spacing=6.25)


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")
