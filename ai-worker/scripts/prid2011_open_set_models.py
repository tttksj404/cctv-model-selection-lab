from __future__ import annotations

from typing import Protocol, Self

import numpy as np


class ProbabilityHeadError(RuntimeError):
    pass


class ProbabilityModel(Protocol):
    def fit(self, features: np.ndarray, labels: np.ndarray) -> Self: ...

    def predict_proba(self, features: np.ndarray) -> np.ndarray: ...

    def state(self) -> dict[str, np.ndarray]: ...


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _class_weights(labels: np.ndarray) -> np.ndarray:
    positives = max(1, int(np.sum(labels)))
    negatives = max(1, len(labels) - positives)
    return np.where(
        labels == 1,
        len(labels) / (2.0 * positives),
        len(labels) / (2.0 * negatives),
    ).astype(np.float32)


class LinearProbabilityHead:
    def __init__(
        self,
        regularization: float,
        learning_rate: float = 0.05,
        iterations: int = 1_000,
    ) -> None:
        self.regularization = regularization
        self.learning_rate = learning_rate
        self.iterations = iterations
        self.mean: np.ndarray | None = None
        self.scale: np.ndarray | None = None
        self.weights: np.ndarray | None = None
        self.bias = 0.0

    def fit(self, features: np.ndarray, labels: np.ndarray) -> Self:
        self.mean = np.mean(features, axis=0)
        self.scale = np.maximum(np.std(features, axis=0), 1e-6)
        standardized = (features - self.mean) / self.scale
        self.weights = np.zeros(standardized.shape[1], dtype=np.float32)
        self.bias = 0.0
        sample_weights = _class_weights(labels)
        for _ in range(self.iterations):
            probabilities = _sigmoid(standardized @ self.weights + self.bias)
            residual = (probabilities - labels) * sample_weights
            gradient = standardized.T @ residual / len(labels)
            gradient += self.regularization * self.weights
            self.weights -= self.learning_rate * gradient
            self.bias -= self.learning_rate * float(np.mean(residual))
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        if self.mean is None or self.scale is None or self.weights is None:
            raise ProbabilityHeadError("linear probability head is not fitted")
        standardized = (features - self.mean) / self.scale
        positive = _sigmoid(standardized @ self.weights + self.bias)
        return np.column_stack((1.0 - positive, positive))

    def state(self) -> dict[str, np.ndarray]:
        if self.mean is None or self.scale is None or self.weights is None:
            raise ProbabilityHeadError("linear probability head is not fitted")
        return {
            "kind": np.asarray("linear"),
            "mean": self.mean,
            "scale": self.scale,
            "weights": self.weights,
            "bias": np.asarray(self.bias),
            "regularization": np.asarray(self.regularization),
        }


class TanhProbabilityHead:
    def __init__(
        self,
        hidden_size: int,
        regularization: float,
        seed: int,
        learning_rate: float = 0.01,
        iterations: int = 600,
    ) -> None:
        self.hidden_size = hidden_size
        self.regularization = regularization
        self.seed = seed
        self.learning_rate = learning_rate
        self.iterations = iterations
        self.mean: np.ndarray | None = None
        self.scale: np.ndarray | None = None
        self.input_weights: np.ndarray | None = None
        self.hidden_bias: np.ndarray | None = None
        self.output_weights: np.ndarray | None = None
        self.output_bias = 0.0

    def _parameters(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if (
            self.mean is None
            or self.scale is None
            or self.input_weights is None
            or self.hidden_bias is None
            or self.output_weights is None
        ):
            raise ProbabilityHeadError("tanh probability head is not fitted")
        return (
            self.mean,
            self.scale,
            self.input_weights,
            self.hidden_bias,
            self.output_weights,
        )

    def fit(self, features: np.ndarray, labels: np.ndarray) -> Self:
        self.mean = np.mean(features, axis=0)
        self.scale = np.maximum(np.std(features, axis=0), 1e-6)
        standardized = (features - self.mean) / self.scale
        rng = np.random.default_rng(self.seed)
        self.input_weights = rng.normal(
            0.0,
            1.0 / np.sqrt(standardized.shape[1]),
            size=(standardized.shape[1], self.hidden_size),
        ).astype(np.float32)
        self.hidden_bias = np.zeros(self.hidden_size, dtype=np.float32)
        self.output_weights = rng.normal(
            0.0, 1.0 / np.sqrt(self.hidden_size), size=self.hidden_size
        ).astype(np.float32)
        self.output_bias = 0.0
        sample_weights = _class_weights(labels)
        for _ in range(self.iterations):
            hidden = np.tanh(standardized @ self.input_weights + self.hidden_bias)
            probabilities = _sigmoid(hidden @ self.output_weights + self.output_bias)
            output_residual = (probabilities - labels) * sample_weights
            output_gradient = hidden.T @ output_residual / len(labels)
            output_gradient += self.regularization * self.output_weights
            hidden_residual = (
                output_residual[:, None]
                * self.output_weights[None, :]
                * (1.0 - hidden**2)
            )
            input_gradient = standardized.T @ hidden_residual / len(labels)
            input_gradient += self.regularization * self.input_weights
            self.output_weights -= self.learning_rate * output_gradient
            self.output_bias -= self.learning_rate * float(np.mean(output_residual))
            self.input_weights -= self.learning_rate * input_gradient
            self.hidden_bias -= self.learning_rate * np.mean(hidden_residual, axis=0)
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        mean, scale, input_weights, hidden_bias, output_weights = self._parameters()
        standardized = (features - mean) / scale
        hidden = np.tanh(standardized @ input_weights + hidden_bias)
        positive = _sigmoid(hidden @ output_weights + self.output_bias)
        return np.column_stack((1.0 - positive, positive))

    def state(self) -> dict[str, np.ndarray]:
        mean, scale, input_weights, hidden_bias, output_weights = self._parameters()
        return {
            "kind": np.asarray("tanh"),
            "mean": mean,
            "scale": scale,
            "input_weights": input_weights,
            "hidden_bias": hidden_bias,
            "output_weights": output_weights,
            "output_bias": np.asarray(self.output_bias),
            "regularization": np.asarray(self.regularization),
        }

