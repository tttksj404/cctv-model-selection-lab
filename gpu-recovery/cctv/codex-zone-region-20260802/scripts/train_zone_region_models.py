from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch import nn

from scripts.build_zone_region_dataset import FEATURE_NAMES, ROUTES, RouteName
from scripts.zone_region_metrics import evaluate_zone_predictions


class ZoneMlp(nn.Module):
    def __init__(self, feature_count: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(feature_count, 64),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 4),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.network(values)


def _load(path: Path, route: RouteName) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    selection_x: list[list[float]] = []
    selection_y: list[int] = []
    sealed_x: list[list[float]] = []
    sealed_y: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["route"] != route:
            continue
        target_x = selection_x if row["cohort"] == "selection" else sealed_x
        target_y = selection_y if row["cohort"] == "selection" else sealed_y
        target_x.append(row["features"])
        target_y.append(int(row["targetZone"]) - 1)
    return (
        np.asarray(selection_x, dtype=np.float32),
        np.asarray(selection_y, dtype=np.int64),
        np.asarray(sealed_x, dtype=np.float32),
        np.asarray(sealed_y, dtype=np.int64),
    )


def _metrics(
    targets: np.ndarray,
    predictions: np.ndarray,
    *,
    train_seconds: float,
    inference_seconds: float,
    device: str,
) -> dict[str, Any]:
    measured = evaluate_zone_predictions(
        tuple(int(value) + 1 for value in targets),
        tuple(int(value) + 1 for value in predictions),
    )
    return {
        **asdict(measured),
        "trainSeconds": train_seconds,
        "inferenceMillisecondsPerSample": inference_seconds * 1000.0 / len(targets),
        "device": device,
        "confusionMatrix": confusion_matrix(targets, predictions, labels=range(4)).tolist(),
    }


def _run_sklearn(
    name: str,
    model: Any,
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    model.fit(train_x, train_y)
    train_seconds = time.perf_counter() - started
    started = time.perf_counter()
    predictions = model.predict(test_x)
    inference_seconds = time.perf_counter() - started
    artifact = output_dir / f"{name}.joblib"
    joblib.dump(model, artifact)
    return {
        **_metrics(
            test_y,
            predictions,
            train_seconds=train_seconds,
            inference_seconds=inference_seconds,
            device="cpu",
        ),
        "artifact": artifact.name,
    }


def _run_mlp(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    torch.manual_seed(20260802)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    fit_x, validation_x, fit_y, validation_y = train_test_split(
        train_x,
        train_y,
        test_size=0.20,
        random_state=20260802,
        stratify=train_y,
    )
    scaler = StandardScaler().fit(fit_x)
    fit_tensor = torch.tensor(scaler.transform(fit_x), dtype=torch.float32, device=device)
    fit_targets = torch.tensor(fit_y, dtype=torch.long, device=device)
    validation_tensor = torch.tensor(
        scaler.transform(validation_x), dtype=torch.float32, device=device
    )
    validation_targets = torch.tensor(validation_y, dtype=torch.long, device=device)
    model = ZoneMlp(train_x.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.001)
    loss_function = nn.CrossEntropyLoss(label_smoothing=0.02)
    best_state: dict[str, torch.Tensor] | None = None
    best_loss = float("inf")
    remaining_patience = 25
    started = time.perf_counter()
    for _ in range(300):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss_function(model(fit_tensor), fit_targets).backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(loss_function(model(validation_tensor), validation_targets))
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            remaining_patience = 25
        else:
            remaining_patience -= 1
            if remaining_patience == 0:
                break
    train_seconds = time.perf_counter() - started
    if best_state is None:
        raise RuntimeError("MLP validation did not produce a checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    test_tensor = torch.tensor(scaler.transform(test_x), dtype=torch.float32, device=device)
    started = time.perf_counter()
    with torch.no_grad():
        predictions = model(test_tensor).argmax(dim=1).cpu().numpy()
    if device.type == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - started
    artifact = output_dir / "gpu_mlp.pt"
    torch.save(
        {
            "featureNames": FEATURE_NAMES,
            "stateDict": best_state,
            "scalerMean": scaler.mean_,
            "scalerScale": scaler.scale_,
        },
        artifact,
    )
    return {
        **_metrics(
            test_y,
            predictions,
            train_seconds=train_seconds,
            inference_seconds=inference_seconds,
            device=str(device),
        ),
        "artifact": artifact.name,
    }


def _run_xgboost(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    from xgboost import XGBClassifier

    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.04,
        subsample=0.90,
        colsample_bytree=0.90,
        objective="multi:softprob",
        device="cuda",
        tree_method="hist",
        random_state=20260802,
    )
    result = _run_sklearn("gpu_xgboost", model, train_x, train_y, test_x, test_y, output_dir)
    result["device"] = "cuda"
    return result


def _run_catboost(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=500,
        depth=7,
        learning_rate=0.04,
        loss_function="MultiClass",
        task_type="GPU",
        devices="0",
        random_seed=20260802,
        verbose=False,
    )
    result = _run_sklearn("gpu_catboost", model, train_x, train_y, test_x, test_y, output_dir)
    result["device"] = "cuda"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare four-zone ranking models on sealed data")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for route in ROUTES:
        train_x, train_y, test_x, test_y = _load(args.dataset, route)
        route_dir = args.output_dir / route
        route_dir.mkdir(parents=True, exist_ok=True)
        final_indices = tuple(
            FEATURE_NAMES.index(f"final_zone_{zone_id}") for zone_id in range(1, 5)
        )
        started = time.perf_counter()
        baseline = test_x[:, final_indices].argmax(axis=1)
        baseline_seconds = time.perf_counter() - started
        route_results = {
            "posterior_argmax": _metrics(
                test_y,
                baseline,
                train_seconds=0.0,
                inference_seconds=baseline_seconds,
                device="cpu",
            ),
            "logistic": _run_sklearn(
                "logistic",
                LogisticRegression(max_iter=2000, C=1.0),
                train_x,
                train_y,
                test_x,
                test_y,
                route_dir,
            ),
            "extra_trees": _run_sklearn(
                "extra_trees",
                ExtraTreesClassifier(
                    n_estimators=800,
                    min_samples_leaf=2,
                    max_features="sqrt",
                    n_jobs=-1,
                    random_state=20260802,
                ),
                train_x,
                train_y,
                test_x,
                test_y,
                route_dir,
            ),
            "hist_gradient_boosting": _run_sklearn(
                "hist_gradient_boosting",
                HistGradientBoostingClassifier(
                    max_iter=400,
                    learning_rate=0.05,
                    max_leaf_nodes=31,
                    l2_regularization=0.01,
                    random_state=20260802,
                ),
                train_x,
                train_y,
                test_x,
                test_y,
                route_dir,
            ),
            "gpu_mlp": _run_mlp(train_x, train_y, test_x, test_y, route_dir),
        }
        for name, runner in (("gpu_xgboost", _run_xgboost), ("gpu_catboost", _run_catboost)):
            try:
                route_results[name] = runner(train_x, train_y, test_x, test_y, route_dir)
            except (ImportError, ModuleNotFoundError, RuntimeError) as error:
                route_results[name] = {"status": "unavailable", "reason": str(error)}
        results[route] = route_results
    eligible = [
        (route, model, metrics)
        for route, models in results.items()
        for model, metrics in models.items()
        if "wilson95_lower" in metrics
    ]
    selected_route, selected_model, selected_metrics = max(
        eligible,
        key=lambda item: (item[2]["wilson95_lower"], item[2]["accuracy"]),
    )
    payload = {
        "schemaVersion": "eyesonu-zone-region-model-comparison-v1",
        "datasetSha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cudaAvailable": torch.cuda.is_available(),
            "gpuCount": torch.cuda.device_count(),
            "gpuName": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "selectionRule": "maximum sealed Wilson 95% lower bound, then accuracy",
        "selected": {
            "route": selected_route,
            "model": selected_model,
            "metrics": selected_metrics,
        },
        "results": results,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
