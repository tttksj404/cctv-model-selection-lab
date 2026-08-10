from typing import Self

import numpy as np
from numpy.typing import NDArray

class CatBoostClassifier:
    def __init__(
        self,
        *,
        iterations: int,
        depth: int,
        learning_rate: float,
        loss_function: str,
        task_type: str,
        devices: str,
        random_seed: int,
        verbose: bool,
    ) -> None: ...
    def fit(self, X: NDArray[np.float32], y: NDArray[np.int64]) -> Self: ...
    def predict(self, X: NDArray[np.float32]) -> NDArray[np.int64]: ...

