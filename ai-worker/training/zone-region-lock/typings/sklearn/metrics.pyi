from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

def confusion_matrix(
    y_true: NDArray[np.int64],
    y_pred: NDArray[np.int64],
    *,
    labels: Iterable[int] | None = ...,
) -> NDArray[np.int64]: ...

