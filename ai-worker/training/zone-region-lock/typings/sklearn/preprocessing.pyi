from typing import Self

import numpy as np
from numpy.typing import NDArray

class StandardScaler:
    mean_: NDArray[np.float64]
    scale_: NDArray[np.float64]
    def fit(self, X: NDArray[np.float32]) -> Self: ...
    def transform(self, X: NDArray[np.float32]) -> NDArray[np.float32]: ...

