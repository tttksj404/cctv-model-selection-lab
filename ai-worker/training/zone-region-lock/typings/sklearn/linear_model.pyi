from typing import Self

import numpy as np
from numpy.typing import NDArray

class LogisticRegression:
    def __init__(self, *, max_iter: int = ..., C: float = ...) -> None: ...
    def fit(self, X: NDArray[np.float32], y: NDArray[np.int64]) -> Self: ...
    def predict(self, X: NDArray[np.float32]) -> NDArray[np.int64]: ...

