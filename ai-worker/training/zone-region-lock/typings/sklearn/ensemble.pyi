from typing import Self

import numpy as np
from numpy.typing import NDArray

class ExtraTreesClassifier:
    def __init__(
        self,
        *,
        n_estimators: int = ...,
        min_samples_leaf: int = ...,
        max_features: str = ...,
        n_jobs: int | None = ...,
        random_state: int | None = ...,
    ) -> None: ...
    def fit(self, X: NDArray[np.float32], y: NDArray[np.int64]) -> Self: ...
    def predict(self, X: NDArray[np.float32]) -> NDArray[np.int64]: ...

class HistGradientBoostingClassifier:
    def __init__(
        self,
        *,
        max_iter: int = ...,
        learning_rate: float = ...,
        max_leaf_nodes: int | None = ...,
        l2_regularization: float = ...,
        random_state: int | None = ...,
    ) -> None: ...
    def fit(self, X: NDArray[np.float32], y: NDArray[np.int64]) -> Self: ...
    def predict(self, X: NDArray[np.float32]) -> NDArray[np.int64]: ...
