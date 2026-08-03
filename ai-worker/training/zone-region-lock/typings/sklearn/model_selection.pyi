import numpy as np
from numpy.typing import NDArray

def train_test_split(
    X: NDArray[np.float32],
    y: NDArray[np.int64],
    *,
    test_size: float = ...,
    random_state: int | None = ...,
    stratify: NDArray[np.int64] | None = ...,
) -> tuple[
    NDArray[np.float32],
    NDArray[np.float32],
    NDArray[np.int64],
    NDArray[np.int64],
]: ...
